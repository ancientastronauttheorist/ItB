# Observatory native capture campaign

## Current boundary

The reversible owner track now contains deterministic callback identities,
exact callback-slot bindings, six build-keyed seeded Lua-RNG pairs, five
natural callback pairs, two counterbalanced atomic native-RNG captures, three
source-verified `Spawner:NextPawn` spans, three counterbalanced spawn-replay
pairs, three coordinate hardware-observer triplets, three same-process
coordinate/RNG-core captures, and three counterbalanced control/dormant/armed
selected-record triplets.
Both seeded native checkpoints include
the fixed seed's first core result, bind every caller to the exact executable
catalog, and report clean byte restoration. The later spans resolve the normal
three-draw `NextPawn` call order. The replay pairs recover an exact observable
MSVC pre-call state class and reproduce each captured pawn from the exported
ratios and candidate order. The hardware observer correlates the reviewed final
selected record to the immediate Pawn queue commit in all three armed trials.
All achievements are complete, and the user explicitly
authorized runtime research in the current owner installation. Evidence from
that installation is accepted for practical, build-keyed Observatory work when
the reversible-owner gate below passes. It is labelled `owner_local_modified`;
it does not prove that an uninstrumented pristine Steam depot is neutral.

The 2026-08-22 callback/native series is closed: a later receipt binds the
restored 33-file save tree, a 689/689 accepted-install comparison, the exact
baseline Mod Loader, zero active Observatory files, and a stopped game process.
The later spawn-span/selected-queue series is independently closed by
`windows_build_13725832_owner_local_modified_20260822_native_boundaries_cleanup_receipt.json`
with the same exact save, install, loader, bridge, and process checks.
The spawn-replay series is closed by
`windows_build_13725832_owner_local_modified_20260822_spawn_replay_cleanup_receipt.json`;
its post-cleanup inventory again matches all 689 accepted entries and the same
33-file save tree.
The coordinate-only and combined coordinate/RNG series are closed by
`windows_build_13725832_owner_local_modified_20260822_spawn_coordinate_rng_cleanup_receipt.json`
with another 689/689 match, the same sealed save tree, the exact baseline Mod
Loader, no active Observatory file, and a stopped game process.

There are now two accepted capture tracks:

1. **Reversible owner track (current).** Inventory the exact owner build, make
   and verify an exact profile/settings/installed-module backup, hash every
   experimental module, capture matched tracing-disabled and tracing-enabled
   trials from the same state, and restore plus re-inventory afterward. This
   track is sufficient for build-keyed callback identities, conformance tests,
   and solver corrections when the evidence is deterministic and the receipt
   states the local modifications.
2. **Pristine-reference track (optional follow-up).** Use a separately
   inventoried fresh Steam download, preferably under a dedicated Windows user
   and Steam identity, when the desired claim specifically concerns pristine
   stock-depot neutrality. A copied install is not acceptable for that claim.
   Steam documents separate family-member saves and achievements in its
   [Steam Families FAQ](https://help.steampowered.com/en/faqs/view/054C-3167-DD7F49D4),
   and its [Cloud support page](https://help.steampowered.com/en/faqs/view/68D2-35AB-09A9-7678)
   documents the per-game Cloud control.

Windows Sandbox is not a fallback on this machine. It is a disposable virtual
machine, requires hardware virtualization and the Windows optional feature,
and its installation may require an administrator. See Microsoft's
[Windows Sandbox prerequisites](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-install).

A separate Windows user is no longer a hard requirement for the current
campaign. It remains the preferred way to obtain a pristine-reference claim;
the current owner track instead relies on exact before/after evidence and must
not be relabelled as clean stock.

## Repository readiness

| Track | Repository state | Runtime state |
|---|---|---|
| Exact PE boundaries | Verified for Windows build `13725832` and executable SHA-256 `31fe3526...4493fe9` | Every live native checkpoint revalidated the exact build identity |
| RNG caller identity | Stable IDs for all 118 raw calls to the shared core; 11 reviewed and 107 explicitly unclassified | Two complete captures observed 28/29 distinct catalogued IDs and no ID 0; reviewed IDs 19, 21, 25, 29, 30, and 31 occur in both |
| Hook-neutrality trials | Strict control/exact-hook suite for one-argument `random_int` and `random_bool`, seeded schema-v2 result contract, exact outcome comparator, and rejected-pair archive | Six seeded direct-boundary matches; only two of six whole-game outcomes matched, so whole-game wrapper neutrality remains unproven |
| Native checkpoint | Reproducible build-keyed RNG-core observer, exact hook/restore manifests, bounded checkpoint schema, one-purpose seed-control helper, and atomic seed-and-arm command | Two accepted checkpoints contain 1,481 and 1,501 records, zero integrity errors, one thread, and exact hook restoration |
| Callback identities and slots | Inert runtime enumeration, bounded enemy-root discovery, exact lexical join, and raw defining-table resolution | Complete: 81 roots, 324 method records, 65 exact slots; two updated fresh-process slot captures are byte-identical |
| Callback hook trials | One-family controller/capsule/host/result path for `ScorePositioning`, `GetTargetScore`, `GetTargetArea`, and `GetSkillEffect` | Five natural pairs completed: 622 attempts, 620 bounded events, every slot restored, no serialization/restore errors; three whole outcomes matched and both repeated `GetSkillEffect` pairs differed only at the spawn marker |
| Callback gameflow helper | Build-keyed, one-export in-process Continue/End Turn helper with no OS-input surface and fail-closed live-screen identity checks | Two independent `/Brepro` builds produced byte-identical 78,848-byte modules and byte-identical normalized receipts; the generated DLL is omitted |
| Spawn RNG | Source-verified `Spawner:NextPawn` span/replay ledgers, exact MSVC observable-state recovery, coordinate hardware observation, same-process RNG attribution, and a Rust non-fabrication safeguard | Three pawn replays reproduce `Firefly2`, `Scarab2`, and `Firefly2`. Three coordinate captures prove ordered-candidate modulo selection at direct caller 60; ordinals 1495/1475/1450 vary because the shared stream includes presentation draws. Ordinary solver input still lacks selector-time state or complete upstream replay |
| Selected action | Build-keyed x86 hardware observer plus strict selected-to-queue correlator | Three counterbalanced control/dormant/armed triplets match semantically; every armed trial records one final selected record immediately followed by the same pawn's queue commit, with `aiDest` = origin, `aiTarget` = target/shot, and weapon = skill |
| Authoritative schema-v2 trace | Existing codec/finalizer/store remain unchanged | No native diagnostic is promoted automatically |

The diagnostic checkpoint is deliberately separate from authoritative
schema-v2 traces. Even a complete checkpoint proves only build-specific facts.
Promotion requires a reviewed semantic mapping and matched neutrality evidence.

## Dormant callback-manifest command

`python game_loop.py observatory_callback_manifest` is an explicit diagnostic
command and is never called by normal play. It loads the sibling
`observatory_callback_manifest.lua` only when requested, then walks the exact
`PawnList` registry with bounded raw/table-only inheritance resolution. It
selects `TEAM_ENEMY` pawn prototypes, resolves their exact `SkillList` globals,
adds the distinct global `ScorePositioning` function, and records function
identity metadata without calling or wrapping any candidate callback. It never
scans `_G`, requires no combat Board for discovery, and fails closed on
malformed registries, dynamic `__index` functions, cycles, or cap exhaustion.
If an exact enemy `SkillList` symbol has no runtime global, discovery preserves
the symbol as an empty callback surface whose four methods are all `missing`.
This covers the shipped, commented-out `Garden_Atk` global without silently
dropping the pawn identity or inventing a callback.
The ordinary file bridge polls commands only from `Mission.BaseUpdate`, so the
live CLI transport requires an unpaused deployment or active mission with a
fresh heartbeat. For a registry-only capture before a Mission exists, a second
explicit path uses the fixed token
`observatory-callback-manifest-request/1` in
`itb_observatory_callback_manifest.request`. At script-load time the bridge
reads at most 129 bytes, removes that one-shot request before execution, accepts
only the exact token (with an optional terminal newline), and invokes the same
literal no-argument command. It never evaluates request content as Lua or as a
general bridge command. Because `scripts.lua` loads `modloader.lua` after the
shipped pawn and skill registries, this path can enumerate them from the title
screen without a Board.

The game publishes the bounded JSON document atomically as
`itb_observatory_callback_manifest.json` in the platform bridge directory and
then emits only a short count ACK. Python requires a changed file generation,
valid JSON, ACK-count agreement, and the strict runtime manifest schema before
reporting success. Exact Lua symbol case is retained in root IDs such as
`enemy.skill.ScorpionAtk1`; the separate global root is
`global.ScorePositioning`.

Deploy this command only inside an accepted capture track. Copy both
`src/bridge/modloader.lua` and
`src/bridge/observatory_callback_manifest.lua` as sibling scripts, record their
hashes in the experiment receipt, and either arm the exact startup request
before restarting ITB or invoke the live command during deployment before any
action. The bridge result file is scratch output, not authoritative evidence;
archive it only through the build-keyed, create-only campaign workflow.

## First owner-track callback capture

On 2026-08-21, a read-only comparison of the owner installation against
`windows_build_13725832_31fe35265598_local_modified.json` found all 689
inventoried files identical, with no changed or missing files. Its installed
`modloader.lua` was the exact Git blob from commit `a1c9e79d`, SHA-256
`8d765cb4d501f1cdc83a6423ad7c2f66e01d98844ec3e8afd1f3c099e4763c10`.
Before instrumentation, the 30-file `profile_Alpha` tree plus `settings.lua`,
`log.txt`, `steam_autocloud.vdf`, and the installed bridge were copied to
`codex_backups/20260821_1505_observatory_owner_before` and verified byte for
byte. The final capture versions of the diagnostic `modloader.lua` and sibling
callback module had SHA-256 values
`46f89fc9da7a1dee07c8922a20e541058e91342b30f523134e142ede70d910a6` and
`c6e6b3db8e97cfcc746f6550b48ef998e2fbab063389ddf2eccba926bdd1fef2`;
the exact 40-byte startup request had SHA-256
`a978e9d687f118110359877f8328ef03e978758fc7a4c9c38daaa839fd037798`.

The first request failed closed before publishing a partial manifest because
`PawnList` references `Garden_Atk`, whose runtime global is absent because its
shipped definition is commented out. The revised collector preserves that
exact symbol with four `missing` methods. Two later fresh-process title-screen
captures were byte-identical: 79,121 bytes, SHA-256
`bbd44cbcf979e6b6c0f9717ffe7fbcae6a60e03b0316d1738168fea89de08d82`.
Each records 81 roots, 324 method slots, 238 resolved methods, 86 missing
methods, and 65 unique Lua function objects. The 86 missing slots are fully
structural: `ScorePositioning` on the 79 implemented skill roots, the three
skill methods on the global root, and all four methods on `Garden_Atk`.

The runtime inventory exposed 13 Advanced Edition boss definitions outside the
original lexical scope, so the build-keyed source index was widened to all 108
relevant files. It now contains 757 definition instances, 756 unique
path/symbol pairs, 410 provenance-indexed callbacks, and 347 explicitly
unindexed callbacks. All 65 runtime function objects join to one exact
hash-verified source path and definition line, with no ambiguous, unmatched,
C, debug-unavailable, truncated, or unresolved entries. The committed join has
SHA-256
`4b52b7ec48702ffafe90ac2db22c644fe270941fae0b211f0548411cc02077fb`.

Cleanup restored and verified all 34 backed-up files (2,600,194 bytes), removed
the experimental module and side-band files, and found no extra profile files.
A full post-restore inventory matched all 689 starting install files exactly:
zero changed, missing, or platform-specific entries. The sealed receipt is
`data/observatory/captures/windows_build_13725832_owner_local_modified_20260821_callback_receipt.json`.
This proves deterministic build-keyed callback identity and exact cleanup. It
does not prove callback behavior, native ABI/hook safety, candidate ordering or
scores, RNG call order, selected actions, Rust equivalence, or pristine-depot
neutrality.

## Rejected RNG pair 004 and seeded campaign

The first complete `_G.random_int` control/exact-hook pair reached the same
`Mission_Power` turn-1 enemy boundary from the sealed 33-file save tree
`ca305830ca471c3d5f1501bb8750a7d076283752bde39a66f637717e7f04eae5`.
The exact condition installed only the return-preserving Lua-global wrapper,
observed one call, returned the original value, published one valid schema-v2
trace event, and restored the global. The control probe returned `4678`; the
exact-hook probe returned `337`. The post-transition bridge states then differed
at `/spawning_tiles/0/0` (`6` versus `5`). This pair is therefore rejected from
neutrality evidence. It proves that a fresh process plus the same save-derived
identity does not reconstruct the same hidden native RNG cursor; it does not
prove that the wrapper caused the spawning-tile difference.

The create-only negative-evidence receipt is
`data/observatory/captures/windows_build_13725832_owner_local_modified_20260821_rng_pair004_rejected_receipt.json`.
It binds both legacy results, the finalized trace, the exact outcome comparison,
the build identity, and the restored save-tree hash.

To remove that confound, the repository now contains a one-purpose x86 seed
helper and reproducible builder. The DLL has exactly one export,
`luaopen_itb_observatory_rng_seed`; exposes only `seed`; verifies the full pinned
PE identity plus exact RNG-core and seed-setter bytes at runtime; and has no
detour, arbitrary memory, remote-process, file, socket, or clock surface. Two
independent `/Brepro` builds produced the same 73,728-byte module SHA-256,
`bd6501c701b8c5f21dbaec309573ab654c7cf01a5705423e2c0ee554dd0e2787`,
and the normalized receipts were byte-identical. Its committed receipt is
`data/observatory/native/windows_build_13725832_31fe35265598_rng_seed_helper_receipt.json`;
the DLL itself is reproducible and is not committed. A title-screen startup
smoke test proved that the module loaded, opened, and passed its internal build
guard.

The replacement host seeds both control and exact-hook conditions immediately
at the exact enemy boundary and requires the mathematically predicted first CRT
draw. The same fail-closed capsule/host/result path independently supports the
one-argument `_G.random_int(bound)` and `_G.random_bool(argument)` boundaries;
each pair installs exactly one matching global and records the family-specific
integer or Boolean payload. Pairs 007 through 012 completed as three
`random_int` and three `random_bool` pairs with counterbalanced condition order.
All six direct probes returned the mathematically predicted value, emitted one
valid event in the exact condition, and restored the selected global. Two
whole-game outcomes matched; four differed only at `/spawning_tiles/0/1`.
The sealed campaign receipt therefore classifies the boundary as
`return_preserving_but_not_whole_game_neutral`. It does not blame the wrapper;
it proves that the present reset/seed boundary does not control every input to
native spawn-coordinate selection. Pair 004 must never be reinterpreted as a
neutral pair.

The campaign is archived at
`data/observatory/captures/windows_build_13725832_owner_local_modified_20260821_seeded_rng/`,
with the build-keyed summary in
`windows_build_13725832_owner_local_modified_20260821_seeded_rng_campaign_receipt.json`.
That immutable receipt records install restoration as pending at its sealing
time. The subsequent
`windows_build_13725832_owner_local_modified_20260822_native_campaign_cleanup_receipt.json`
closes the pending state with a 689/689 install comparison, the restored
33-file save tree, and zero active Observatory bridge files.

## Atomic native-RNG campaign

The first native trials seeded and armed with two consecutive bridge commands.
Their exact streams exposed a one-tick race: one run began with result `24356`,
while a later run began with the following result `2578`. The final boundary
therefore uses one Lua dispatch,
`OBS_NATIVE_RNG_SEED_AND_ARM <capture_id>`, which loads and validates both
pinned helpers while the RNG bytes are pristine, applies seed `324508639`, and
arms the observer without returning to a game tick.

Two fresh-state pairs then ran in opposite condition order. Their exact
checkpoints contain 1,481 and 1,501 records, are single-threaded, contain no
unknown caller, overflow, torn record, or restore conflict, and report the
trusted RNG-core hash after restoration. Both begin with native result `24356`.
The first 104 result values repeat, although the caller/result tuple differs at
the first record and the streams diverge afterward. Reviewed callers for AI
seed advance, one-argument `random_int` and `random_bool`, candidate-loop
tie-breaking, and both record-selector sites appear in both checkpoints. The
candidate-loop, record-selector, and seed-advance result subsequences repeat;
the later `random_int`/`random_bool` leaf subsequences do not.

Both exact observed outcomes are semantically identical after removing the
bridge timestamp and select spawn `[6, 5]`. The controls, restored from the
same sealed save and seeded identically, select `[5, 4]` and `[5, 2]`.
Within each pair, the only semantic difference is the next spawn coordinate.
This is useful negative evidence: fixed native seed plus save state does not
define a reproducible linear spawn-selection experiment on this runtime, and
the observer cannot be called whole-game neutral. It does not justify a guessed
spawn algorithm. Rust therefore retains the conformance safeguard that it may
consume observed markers but never fabricate an unknown pawn or replacement
coordinate.

The build-keyed artifacts and deterministic validator are under
`data/observatory/captures/windows_build_13725832_owner_local_modified_20260822_native_rng_core_atomic/`.
The campaign receipt is
`windows_build_13725832_owner_local_modified_20260822_native_rng_core_atomic_receipt.json`.
At sealing time it explicitly left `Spawner:NextPawn` draw attribution,
observer neutrality, and native selected-record semantics unproven. The later
bounded campaigns below close the first and third gaps without retroactively
promoting the native RNG observer as whole-game neutral.

## Exact callback slots and natural-call trials

The callback binding collector resolves each published method through raw
table-only inheritance to its actual defining holder. Shared inherited methods
become one slot rather than stacked wrappers. The current build resolves 65
slots: 11 `GetTargetArea`, 15 `GetTargetScore`, 38 `GetSkillEffect`, and one
global `ScorePositioning`. Two fresh processes using the final live-holder
collector produced the same 131,137 bytes, raw SHA-256
`39f1dda91de64a9b4b976a3ed3c12c93ae588ee5bcf6be66731c33b4b91abb24`
and canonical SHA-256
`d6b25a368df6cbe9d556f56c7dc0e94531369d0ac2f97ad5ac0d4a169b7d9eb3`.
Enumeration calls and wraps no candidate.
`windows_build_13725832_owner_local_modified_20260822_callback_bindings_receipt.json`
binds both fresh-process artifacts, the exact collector source hashes, and the
family counts.

`observatory_callback_controller.lua` consumes that exact slot document and a
complete source join, permits exactly one family, and wraps every defining slot
in that family together. Its adapters run only after the original callback,
preserve the complete return tuple and original error, bound all PointList and
SkillEffect extraction, and admit only primitive JSON data. The one-shot host
constructs inertly at script load, arms at the natural enemy `NextTurn`
boundary, checkpoints after the following `BaseUpdate`, and verifies every
holder is restored before publishing a result. Control runs prepare the same
packet without installing or writing a hook. Capsule, request, result,
comparison, raw-finalization, and CLI paths are create-only and fail closed.

The live natural-call campaign used the sealed `Mission_Power` turn-1 state and
wrapped one family at a time. It completed one `ScorePositioning` pair (100
attempts/events), one `GetTargetArea` pair (47/47), one `GetTargetScore` pair
(181/181), and two counterbalanced `GetSkillEffect` pairs (147 attempts and 146
bounded events each). Every pair covered exactly one enemy decision cycle,
restored every installed slot, and reported no serialization or restoration
error. The one dropped event in each `GetSkillEffect` trace is an explicit
`max_total_event_bytes` bound, not a callback failure; the original call still
returned normally.

The `ScorePositioning`, `GetTargetArea`, and `GetTargetScore` control/exact
bridge outcomes match in full except for timestamp. Both `GetSkillEffect`
repetitions produce byte-equivalent event lists and repeat their respective
control and exact outcomes, but the paired conditions differ at only the next
spawn coordinate (`[6, 5]` versus `[5, 3]`). Therefore the campaign proves
natural invocation and safe restoration for all four families, not general
whole-game neutrality. Because every other bridge field matches, the final
queued enemy actions also match within all five pairs. At this stage direct
native selected-record correlation and native candidate-enumeration records
remained separate gaps; the later selected-queue campaign closes the former
for its bounded Firefly scenario.

The archived pairs and strict receipt are under
`data/observatory/captures/windows_build_13725832_owner_local_modified_20260822_natural_callbacks/`
and
`windows_build_13725832_owner_local_modified_20260822_natural_callback_campaign_receipt.json`.

The host's gameflow helper invokes only the exact reviewed title Continue and
battle End Turn boundaries after validating the pinned executable, SDL frame
bridge, active screen registry, and battle UI identities. It exposes no cursor,
keyboard, message, remote-process, file, network, or general memory surface.
Two independent deterministic builds produced the same 78,848-byte DLL and
the same normalized receipt. The DLL is not committed; the source, builder,
build receipt, and two-build reproducibility receipt are committed.

## Spawn-span, spawn-replay, coordinate, and selected-queue campaigns

Three fresh-state spawn pairs counterbalanced an exact native-RNG checkpoint
against the same checkpoint plus a source-verified `Spawner:NextPawn` span.
Every complete span encloses exactly three consecutive native draws, all from
reviewed caller ID 21 (`random_int(max)`). Joined to the exact shipped
`spawner_backend.lua` bytes, their order is:

1. `random_int(curr_weakRatio[2])` for weak versus non-weak class;
2. `random_element(available)` for pawn identity; and
3. `random_int(curr_upgradeRatio[2])` for upgrade class.

The optional boss `random_bool(chance)` branch did not execute. The selected
pawns were `Firefly2`, `Scarab2`, and `Scarab2`; all native bytes and Lua
wrappers restored cleanly. One paired whole-game outcome matched, while two
differed only at the later spawn-coordinate marker. This resolves the ordinary
`NextPawn` call order, not replay: ordinary solver state still lacks the
pre-span CRT cursor and exact runtime `available` array order, and coordinate
selection occurs outside `NextPawn`. The immutable receipt is
`windows_build_13725832_owner_local_modified_20260822_spawn_span_receipt.json`.

The follow-up replay campaign wrapped only the exact source-verified
`Spawner.NextPawn` slot and, synchronously inside that call, the exact
`random_element` slot. Three control/replay pairs used the same sealed save and
counterbalanced order. Every replay exported one ordered candidate array, the
effective weak and upgrade ratios, and three consecutive reviewed caller-21
results. Those results recover two raw MSVC pre-call states differing only by
`0x80000000`; their canonical low-31-bit state produces the same observable
stream forever. Replaying the recovered states reproduces `Firefly2`,
`Scarab2`, and `Firefly2` exactly. One paired whole-game outcome matched; two
differed only at the following spawn coordinate. Because each fresh process had
a naturally seeded native state, this is exact in-span replay and restoration
evidence, not an exactly state-matched whole-game neutrality result. Ordinary
solver input also does not yet receive the capsule before the call, and the
coordinate scheduler remains a separate boundary. The immutable campaign and
cleanup receipts are
`windows_build_13725832_owner_local_modified_20260822_spawn_replay_receipt.json`
and
`windows_build_13725832_owner_local_modified_20260822_spawn_replay_cleanup_receipt.json`.

The coordinate campaign uses x86 hardware breakpoints at the reviewed
scheduler append, fallback selector, and standard selector seams; it modifies
no executable bytes. Three counterbalanced control/dormant/armed triplets
capture the same ordered candidates `[[5,2],[5,3],[5,4],[6,2],[6,5]]` in every
armed trial. The observed standard selector results `5290`, `3963`, and `20348`
select indices `0`, `3`, and `3` by exact modulo and match the bridge spawn
marker. Scheduler and fallback paths did not execute. The immutable receipt is
`windows_build_13725832_owner_local_modified_20260822_spawn_coordinate_receipt.json`.

The follow-up offline path map
`windows_build_13725832_31fe35265598_spawn_coordinate_paths.json` resolves what
those dormant seams mean without promoting them as naturally exercised.
Caller 59 is guarded by the literal emergency-placement branch after ordinary
candidates are exhausted and uses the same exact modulo rule. Caller 66
randomizes a supplied point vector without replacement for opaque predicate
checks, then invokes the ordinary selector separately if the path proceeds; it
does not return the sampled point as the final coordinate. Runtime predicate
inputs remain capture-on-demand evidence.

The follow-up combined campaign prepares that hardware observer first and then
atomically seeds and arms the RNG-core observer, so both transcripts cover the
same End Turn in one process. Caller 60 at `0x00172e70` uniquely matches the
coordinate draw in all three checkpoints. Its zero-based sequences are 1494,
1474, and 1449 (ordinals 1495, 1475, and 1450), and its raw values are `3642`,
`15777`, and `30530`. A separate build-keyed static overlay preserves the
original return-map digest while classifying every caller whose count varied.
Presentation domains contribute 1271, 1250, and 1225 upstream draws; particle
emitters vary by 45 draws and `UnitAcid` effects by 36. Environment-XP and the
reviewed Lua `random_int` boundary vary by one draw each. The classified count
deltas `[0,-20,-45]` exactly equal the selector-ordinal deltas, with no varying
caller left unclassified. This resolves the direct caller and the cause of the
unstable ordinal; it does not make a future coordinate predictable from
ordinary save/solver state. The immutable evidence and closure receipts are
`windows_build_13725832_owner_local_modified_20260822_spawn_coordinate_rng_receipt.json`
and
`windows_build_13725832_owner_local_modified_20260822_spawn_coordinate_rng_cleanup_receipt.json`.

The selected-action campaign used a build-keyed x86 hardware-breakpoint
observer that modifies no executable bytes. Each of three fresh-state triplets
ran `control`, dormant-loaded, and armed conditions in a different order. All
nine semantic outcomes match. Every armed capture contains exactly one final
24-byte selected record followed immediately on the same thread by one queue
commit for pawn 1303 (`Firefly1`): `aiDest [5,4]` equals queue origin,
`aiTarget [4,4]` equals queue target and shot, and current weapon 1 equals
queued skill 1. The bridge independently corroborates the target ray. Every
debug register was cleared, the vectored exception handler was removed, seam
bytes were unchanged, and no executable file bytes changed. This is a bounded
one-pawn proof, not a universal claim about cancellation, retargeting, or every
enemy type. The immutable receipt is
`windows_build_13725832_owner_local_modified_20260822_selected_queue_receipt.json`.

The later
`windows_build_13725832_owner_local_modified_20260822_native_boundaries_cleanup_receipt.json`
closes both receipts' pending restore fields. It binds a 689/689 install match,
the exact 33-file save tree, the baseline Mod Loader hash, zero active
Observatory files, and a stopped game process.

## Capture-track acceptance gate

Before the first experimental launch, record and verify all common items:

- the Windows user and Steam identity are recorded;
- the exact starting install has a deterministic Observatory inventory and an
  explicit provenance label (`owner_local_modified` or `pristine_reference`);
- the executable, Lua DLL, scripts, maps, app manifest, depot manifest, and
  native libraries match the boundary artifacts or are classified as a new
  build requiring a new static pass;
- the profile, settings, bridge, and evidence roots are recorded after link
  resolution;
- the active profile/settings and installed integration have a verified,
  recoverable byte-exact backup;
- every helper, controller, hook plan, and scenario has an exact SHA-256;
- the scenario and starting state are recorded, and no normal play action is
  mixed into a capture pair;
- every result and receipt carries the capture-track label.

The pristine-reference track additionally requires a fresh Steam download in a
disjoint library, no copied owner save/profile, and a deterministic stock
inventory. The reversible-owner track additionally requires explicit user
authorization, a create-only durable evidence copy, matched trials from the
same reset state, and an exact post-trial restore comparison. Steam Cloud should
be disabled or Steam kept offline during owner-track mutation as defense in
depth; the verified local backup remains the recovery authority.

Any failed common or track-specific item blocks launch or hook installation. A
new executable hash
invalidates every recorded RVA and the committed RNG caller-ID catalog.
The native checkpoint's `rng_return_map_sha256` is the SHA-256 of the catalog's
deterministic encoded bytes, including its final newline; attribution rejects a
catalog whose digest or executable identity differs. Its externally trusted
identity also binds `hook_plan_sha256` and the canonical
`restore_manifest_sha256`. Reported restoration is not complete evidence until
the observed post-restore hashes exactly equal that trusted manifest.

## Native helper contract

The seed-control helper described above is not an observer or hook: it invokes
only the reviewed seed setter from the game thread and immediately returns. The
native *observer* is a separate reproducibly built, build-keyed x86 DLL with no
general-purpose injection or remote-control surface. Its hot hook contract is:

- preserve the x86 ABI, registers, flags, stack, return value, and original
  instruction sequence;
- use a fixed-size preallocated ring and fixed-width records;
- perform no allocation, Lua calls, game API calls, file I/O, locks, clocks, or
  serialization in the hook;
- record only sequence, bounded thread slot, caller ID, and the 0..32767 RNG
  result at the RNG-core boundary;
- map the return address to the committed 1..118 catalog and use ID 0 for any
  unknown value; never persist an absolute address or pointer;
- stop diagnostically on overflow, torn writes, an unknown caller, thread-cap
  exhaustion, identity mismatch, or restore conflict;
- restore exact original bytes before checkpoint publication and publish
  post-restore hashes.

Use hardware data breakpoints first to discover writes to the selected-record
fields. Do not place a detour at the selected-record copy until its exact write
and continuation boundaries have been reviewed independently.

## Experiment order

Run one family at a time. Each family needs at least three fresh-state,
counterbalanced control/exact-hook pairs. Hash the scenario and starting state,
use a unique pair nonce and unique receipt nonces, and compare semantic output
exactly. Timing is reported separately; it never excuses output drift.

1. **Control harness only.** Prove deterministic reset, receipts, stock restore,
   and create-only evidence publication without installing a hook.
2. **One Lua global.** Test `_G.random_int`, then `_G.random_bool`, independently.
   These are partial boundaries and must not be labeled as the full RNG stream.
3. **Shared RNG core.** Enable only the fixed-record native core observer. Prove
   caller-ID completeness and behavior neutrality.
4. **Spawn spans (completed for the normal three-draw path).** Add
   `Spawner:NextPawn` enter/exit markers without wrapping RNG. Join enclosed
   native draws, and preserve no-draw shortcuts, reseeds, nesting, and
   ambiguity explicitly.
5. **Spawn replay (completed for three ordinary live calls).** Export the
   effective ratios and exact ordered `available` array while enclosing the
   same-thread native results. Recover the observable MSVC state class and
   fail closed unless the replay reproduces the selected pawn and every wrapper
   restores.
6. **Runtime callback inventory.** Complete for this build: enumerate exact
   loaded method identities and defining slots without wrapping or calling
   them. Re-run this gate for any changed executable or script inventory.
7. **One callback family.** Wrap only reviewed exact function identities for
   `ScorePositioning`, `GetTargetScore`, `GetTargetArea`, or `GetSkillEffect`,
   one family per matched series. Coverage is the runtime manifest, not the
   base class name.
8. **Selected record (completed for the bounded Firefly scenario).** Observe
   the proven 24-byte selected-record write, then take a bridge-visible queue
   snapshot. Correlate `aiDest`, `aiTarget`, and skill only when there is one
   selected record, one immediate queued enemy, and no cancellation or
   retarget.
9. **Candidate tournament.** Only after the narrower boundaries pass, add
   candidate order and score evidence while preserving vector order and native
   equal-best tie breaks.

For each family, archive the suite, both receipts, helper/controller/hook
hashes, raw checkpoint, comparison, and cleanup inventory. A crash, mismatch,
timeout, cap, unknown caller, restore conflict, or semantic difference ends the
series without promotion.

## Cleanup and promotion

After every series, disarm, restore exact hook bytes, stop the helper, remove
the experimental Mod Loader integration, and compare the active install with
its accepted starting inventory. This includes restoring the exact prior
`modloader.lua`, removing the installed callback manifest/bindings modules,
callback/RNG trial hosts, content-addressed controllers and capsules, native
helper/observer DLLs, and every Observatory result, raw, `.tmp`, and request
file from the active bridge directory after its durable copy is verified. On the
pristine-reference track, remove the test profile and experimental evidence
staging area only after durable evidence has been copied to the repository
archive. On the owner track, restore the byte-exact backup and report every
before/after difference; do not claim cleanup if any unexplained difference
remains.

The 2026-08-22 owner-track cleanup completed this gate: the accepted and
post-cleanup inventories compare as 689 identical, zero changed, zero missing;
the 33-file save tree matches its sealed manifest; and no Observatory file
remains in the active installation or bridge. The dry-run-first cleanup command
restored the pinned baseline loader and removed only 62 verified experimental
install files and 32 bridge scratch files; recoverable owner staging was
preserved. The later
`windows_build_13725832_owner_local_modified_20260822_callback_native_campaign_cleanup_receipt.json`
closes the pending save/install fields in both new immutable campaign receipts.
The subsequent spawn-replay cleanup separately removed three verified install
artifacts and two bridge artifacts, restored the same baseline loader, verified
the same 33-file save, and re-established a 689/689 inventory match. Its closure
receipt is
`windows_build_13725832_owner_local_modified_20260822_spawn_replay_cleanup_receipt.json`.

Only repeated, build-keyed results whose restoration and neutrality scope are
stated precisely may become Rust conformance tests or simulator changes. Each
simulator semantic change still follows the normal
version bump, regression archive, rebuild, focused proof, and broader regression
discipline. Unknown or ambiguous captures remain provenance gaps.
