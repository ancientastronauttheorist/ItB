# Observatory native capture campaign

## Current boundary

The repository-side capture groundwork is ready, but no native hook has been
installed and no live capture has begun. All achievements are complete, and
the user has explicitly authorized launching ITB for this research. The owner
installation and profile still remain protected from unproven native detours.
Runtime evidence should come from a separately inventoried test installation;
a copied install is not acceptable as proof of a clean stock baseline.

The non-VM route is:

1. Create a dedicated standard local Windows user for Observatory experiments.
2. Prefer a separate Steam account that owns Into the Breach or legitimately
   has access through Steam Families. Steam documents that achievements are
   tied to individual Steam accounts and that family members have personal
   saves and achievements in its
   [Steam Families FAQ](https://help.steampowered.com/en/faqs/view/054C-3167-DD7F49D4).
   Because this account already has every achievement, using the same Steam
   identity is acceptable only with the separate Windows profile, Cloud
   disabled, an owner-profile backup, and explicit experiment receipts.
3. Install Steam under the test Windows user's profile and perform a fresh Steam
   download into a new library that is not `B:` and is neither a junction nor a
   copy of the owner installation.
4. Disable Steam Cloud for Into the Breach on the test account as defense in
   depth. Steam's
   [Cloud support page](https://help.steampowered.com/en/faqs/view/68D2-35AB-09A9-7678)
   documents the per-game control. This does not replace the separate Steam
   identity.
5. Keep the test profile, bridge directory, raw checkpoints, and finalized
   evidence under the test Windows user. Do not grant them a path into the
   owner's ITB profile.

Windows Sandbox is not a fallback on this machine. It is a disposable virtual
machine, requires hardware virtualization and the Windows optional feature,
and its installation may require an administrator. See Microsoft's
[Windows Sandbox prerequisites](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-install).

The user must create or authorize creation of the Windows test user and log in
to the chosen Steam account. After that, Codex can inventory, validate, install
only into the test tree, run experiments, and clean up without touching the
owner profile. Read-only launches of the existing game are allowed, but do not
establish native-hook neutrality.

## Repository readiness

| Track | Repository state | Runtime state |
|---|---|---|
| Exact PE boundaries | Verified for Windows build `13725832` and executable SHA-256 `31fe3526...4493fe9` | No hook installed |
| RNG caller identity | Stable IDs for all 118 raw calls to the shared core; 11 reviewed and 107 explicitly unclassified | No caller observed |
| Hook-neutrality trials | Strict control/exact-hook suite, receipt, and comparator contracts | Awaiting isolated installation |
| Native checkpoint | Strict bounded diagnostic schema with overflow, unknown-caller, torn-record, and restore gates | No native helper loaded |
| Callback identities | Inert runtime enumeration and exact lexical-inventory join | Awaiting isolated runtime enumeration |
| Spawn RNG | Span-based attribution analyzer with nesting, reseed, shortcut, and ambiguity handling | Awaiting `Spawner:NextPawn` markers |
| Selected action | `aiDest`/`aiTarget` to Pawn queue correlation analyzer | Awaiting selected-record and queue checkpoints |
| Authoritative schema-v2 trace | Existing codec/finalizer/store remain unchanged | No native diagnostic is promoted automatically |

The diagnostic checkpoint is deliberately separate from authoritative
schema-v2 traces. Even a complete checkpoint proves only build-specific facts.
Promotion requires a reviewed semantic mapping and matched neutrality evidence.

## Isolation acceptance gate

Before the first test launch, record and verify all of the following:

- the test Windows user differs from the owner user;
- the Steam identity is recorded; if it matches the owner identity, Cloud is
  disabled and the owner profile has a verified recoverable backup;
- the test install, profile, bridge, and evidence roots are disjoint from all
  owner roots after resolving links;
- the game was freshly downloaded by Steam into the test library;
- the stock test install has a deterministic Observatory inventory;
- the executable, Lua DLL, scripts, maps, app manifest, depot manifest, and
  native libraries match the boundary artifacts or are classified as a new
  build requiring a new static pass;
- Steam Cloud is disabled for the test account and no owner save/profile was
  copied in;
- the owner install and profile hashes are captured as a read-only before-state;
- every helper, controller, hook plan, and scenario has an exact SHA-256;
- the test scenario is synthetic and carries no achievement objective.

Any failed item blocks launch or hook installation. A new executable hash
invalidates every recorded RVA and the committed RNG caller-ID catalog.
The native checkpoint's `rng_return_map_sha256` is the SHA-256 of the catalog's
deterministic encoded bytes, including its final newline; attribution rejects a
catalog whose digest or executable identity differs. Its externally trusted
identity also binds `hook_plan_sha256` and the canonical
`restore_manifest_sha256`. Reported restoration is not complete evidence until
the observed post-restore hashes exactly equal that trusted manifest.

## Native helper contract

Implement the native helper only after the isolation gate passes. The first
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
the experimental Mod Loader integration, and compare the test install with its
stock inventory. At campaign end, remove the test profile and experimental
evidence staging area only after durable evidence has been copied to the
repository archive. Re-hash the owner install/profile and confirm the read-only
before-state did not change.

Only repeated, neutral, build-keyed results may become Rust conformance tests
or simulator changes. Each simulator semantic change still follows the normal
version bump, regression archive, rebuild, focused proof, and broader regression
discipline. Unknown or ambiguous captures remain provenance gaps.
