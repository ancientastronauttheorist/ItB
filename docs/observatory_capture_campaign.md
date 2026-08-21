# Observatory native capture campaign

## Current boundary

The first live, non-invasive callback-identity capture is complete on the
reversible owner track. No native hook was installed, no candidate callback was
called or wrapped, and the owner install was restored exactly afterward. All
achievements are complete, and the user explicitly authorized runtime research
in the current owner installation. Evidence from that installation is accepted
for practical, build-keyed Observatory work when the reversible-owner gate
below passes. It is labelled `owner_local_modified`; it does not prove that an
uninstrumented pristine Steam depot is neutral.

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
| Exact PE boundaries | Verified for Windows build `13725832` and executable SHA-256 `31fe3526...4493fe9` | No hook installed |
| RNG caller identity | Stable IDs for all 118 raw calls to the shared core; 11 reviewed and 107 explicitly unclassified | No caller observed |
| Hook-neutrality trials | Strict control/exact-hook suite, receipt, and comparator contracts | Owner track accepted; matched trials not started |
| Native checkpoint | Strict bounded diagnostic schema with overflow, unknown-caller, torn-record, and restore gates | No native helper loaded |
| Callback identities | Inert runtime enumeration, bounded pre-combat enemy-root discovery, fresh side-band transport, strict validation, and exact lexical-inventory join | Complete: two byte-identical fresh-process manifests; all 65 unique Lua functions joined exactly |
| Spawn RNG | Span-based attribution analyzer with nesting, reseed, shortcut, and ambiguity handling | Awaiting `Spawner:NextPawn` markers |
| Selected action | `aiDest`/`aiTarget` to Pawn queue correlation analyzer | Awaiting selected-record and queue checkpoints |
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

Implement the native helper only after one capture-track gate passes. The first
helper should be a build-keyed x86 DLL with no general-purpose injection or
remote-control surface. Its hot hook must:

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
4. **Spawn spans.** Add `Spawner:NextPawn` enter/exit markers without wrapping
   RNG. Join enclosed native draws, and preserve no-draw shortcuts, reseeds,
   nesting, and ambiguity explicitly.
5. **Runtime callback inventory.** Enumerate exact loaded method identities
   without wrapping or calling them. Review unresolved C functions, function
   `__index` values, cycles, replacements, and ambiguous source/line joins.
6. **One callback family.** Wrap only reviewed exact function identities for
   `ScorePositioning`, `GetTargetScore`, `GetTargetArea`, or `GetSkillEffect`,
   one family per matched series. Coverage is the runtime manifest, not the
   base class name.
7. **Selected record.** Observe the proven 24-byte selected-record write, then
   take a bridge-visible queue snapshot. Correlate `aiDest`, `aiTarget`, and
   skill only when there is one selected record, one immediate queued enemy,
   and no cancellation or retarget.
8. **Candidate tournament.** Only after the narrower boundaries pass, add
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
`modloader.lua`,
removing the installed sibling `observatory_callback_manifest.lua`, and
removing `itb_observatory_callback_manifest.json` plus any `.tmp` file from the
active bridge directory after its durable copy is verified. Also remove any
remaining `itb_observatory_callback_manifest.request`. On the
pristine-reference track, remove the test profile and experimental evidence
staging area only after durable evidence has been copied to the repository
archive. On the owner track, restore the byte-exact backup and report every
before/after difference; do not claim cleanup if any unexplained difference
remains.

Only repeated, neutral, build-keyed results may become Rust conformance tests
or simulator changes. Each simulator semantic change still follows the normal
version bump, regression archive, rebuild, focused proof, and broader regression
discipline. Unknown or ambiguous captures remain provenance gaps.
