# ITB Engine Observatory trace contract

## Status and safety boundary

This document defines a trace evidence contract and its dormant Lua runtime.
The reusable Python codec, strict raw finalizer, and immutable offline store
are implemented in `src/observatory/trace_codec.py`,
`src/observatory/raw_trace.py`, and `src/observatory/trace_store.py`. The
source-only runtime is implemented in `src/bridge/observatory_trace.lua`.
Loading it performs no file I/O, polling, arming, or hook installation. It
requires an exact short-lived manifest, a separate one-shot activation nonce,
an exact trusted policy and full hook plan, a trusted live identity/clock
provider, and an explicit call for each independently proven non-yielding hook.
`scripts/itb_trace.py build-arm|finalize-raw|validate|summary` requires the
appropriate trusted content inventory, capture identity, exact artifact
hashes, and external evidence digests; structural validation alone is not
treated as authoritative.

No trace hook is connected to Mod Loader or installed into the game by this
work. `src/bridge/modloader.lua`, the installed game, the game process, and the
active achievement session remain untouched. Deployment requires a separately
reviewed safe window.

## Goals

The trace must answer narrow fidelity questions without becoming part of game
behavior. Initial event families are:

- `random_int` and `random_bool`: raw arguments, result, real call-site tag,
  accepted-event sequence, and separate attempted `call_order`. Gaps in
  `call_order` are expected when an observation is filtered or dropped, but
  accepted RNG events must retain increasing attempted order. The
  `random_bool` argument is deliberately named `argument`; calls such as
  `random_bool(5)` do not establish percentage semantics.
- `enemy_candidate`: pawn, skill, origin, destination, target, enumeration
  order.
- `enemy_target_score` and `score_positioning`: candidate identity and score.
- `get_target_area` and `get_skill_effect`: primitive summaries of inputs and
  returned areas/effects.
- `enemy_action_selected`: final pawn movement, skill, and target selected by
  the engine.

Every schema-v2 bundle carries the build platform, architecture, executable hash,
numeric build/depot identity plus its evidence source, and scripts/maps
revisions. Hashes are lowercase SHA-256 values. The architecture vocabulary
matches the inventory schema, including ARMv7 and a canonical list of slices
for universal Mach-O builds. Unknown architecture is explicit rather than
guessed; unavailable build evidence requires null build/manifest fields.
Evidence from different identities must not be pooled silently. Authoritative
loading rejects `build_evidence: unavailable` and requires a type-exact match
with the trusted inventory-derived identity.

Each bundle also carries a one-shot capture identity: capture ID and arm nonce,
controller version/hash, installed Mod Loader hash, expected mission/turn,
timeline and AI-seed fingerprints, master seed, region, and a short UTC
activation/expiry window capped at 15 minutes. It also binds the expected phase
and SHA-256 digests of both the exact cap/phase configuration and canonical
hook-coverage manifest. The checkpoint repeats the mission/turn, fixes the
phase, records attempted calls for every event family, and has bounded
start/completion timestamps. Accepted events must match that identity and
checkpoint exactly.

Payloads are event-specific rather than arbitrary JSON. RNG results are checked
against their declared bounds; candidates and actions require pawn, skill,
origin, destination, and target identity; scores must be finite; and all board
coordinates are validated. Target-area evidence uses a versioned coordinate
list. Skill-effect evidence is initially a versioned opaque primitive-summary
hash and count until a safe, complete primitive schema is proven.

## Behavior-neutral invariants

When disabled, no wrapper is installed and no payload is constructed. When
enabled:

1. Call the original function exactly once with unchanged arguments.
2. Let original errors propagate normally; do not put the original call inside
   a trace `pcall`.
3. Preserve every return value, including trailing `nil` values.
4. Run trace extraction/serialization afterward inside its own protected call.
5. Swallow and count trace errors; observation may disappear but gameplay may
   not change.
6. Never retain or mutate engine userdata. Serialize primitive copies and
   summaries only.
7. Keep original functions in a global re-execution guard so reloads cannot
   stack wrappers.
8. Set a `trace_in_progress` reentrancy guard before extraction. If tracing
   recursively reaches another wrapped function, skip the nested observation.
9. Do not call game APIs or wrapped engine callbacks while extracting an event;
   copy only values already available at the boundary.

The runtime owns one observation attempt per wrapper call. It checks the
trusted live identity, phase, and clock before extraction, then supplies the
observer only bounded primitive copies of the arguments, return values, and
runtime identity. Boundaries containing userdata, functions, cycles, or other
non-primitive values fail closed without invoking the observer. The original
call runs before the extraction reentrancy guard is set, so legitimate nested
engine calls remain visible; only observer-triggered recursion is skipped.

The trusted policy is compared field-for-field with the armed caps, phase, and
event allowlist. Every planned installed hook has a unique ID and a frozen
construction-time holder/key/function binding; checkpointing fails if any
planned hook was not installed or is no longer attached. The raw checkpoint
repeats the canonical Python config and hook-coverage digest preimages (the
runtime-only hook IDs stay internal), so offline canonicalization can recompute
both digests. This initial primitive runtime accepts `installed` and `disabled`
coverage entries with source hashes; an `unavailable` target fails arming until
an explicit Lua-null serialization contract is added.
Nonce and wrapper registries live in a process-global table initialized by
runtime construction, so reloading the module cannot replay a nonce or stack a
wrapper. Loading the module alone still creates no global state.

For proven non-yieldable Lua 5.1 functions, a wrapper can preserve multiple
returns with a
`pack(...)= {n=select("#", ...), ...}` helper and
`unpack(results, 1, results.n)`. The direct `pack(original(...))` call preserves
the original error path while guaranteeing one invocation. This pattern must
not be applied generically to functions that may yield: Lua 5.1 yield behavior
across C/Lua wrapper boundaries requires separate proof, and an unsafe wrapper
must not be installed.

The exact-language behavior harness uses the Lua 5.1 runtime bundled by the
optional `lupa.lua51` package:

```powershell
python -m pytest tests/test_observatory_trace_lua.py -q
```

Without that optional package, the test module skips. The isolated harness
proves disabled-load behavior, two-step/replay-safe activation, full capture
identity and bounds, lazy payload construction, primitive-only copies, global
reload-safe wrapper registration, exact return/error behavior, reentrancy,
restoration conflicts, maximum-envelope checkpointing, attempt/outcome
reconciliation, and disarming checkpoints.

## Bounds and phase policy

Tracing is explicit opt-in and defaults to enemy combat only
(`Game:GetTeamTurn() == TEAM_ENEMY` with a cached active mission). The codec
enforces:

- total event count;
- event count per `(mission_id, turn)`;
- canonical compact-JSON bytes per event and in the event collection;
- actual UTF-8 bytes in the persisted, pretty-printed bundle;
- a fixed event-kind allowlist;
- contiguous accepted-event sequence numbers;
- bounded-width observation counters with explicit saturation/truncation;
- truncation and dropped/error counters.

The dormant Lua runtime enforces those byte caps with a conservative
pretty-JSON upper bound rather than claiming to reproduce Python's encoder:
each input string byte reserves the worst-case JSON escape width, numbers and
table entries reserve fixed worst-case syntax/indentation overhead, and the
full event envelope plus its collection delimiter is charged. The raw summary
labels this value `event_byte_upper_bound`; offline canonicalization recomputes
the exact `event_bytes`. Arming also requires
`max_bundle_bytes >= max_total_event_bytes + 2 MiB`, and checkpoint copying is
bounded by `max_bundle_bytes`, so the published Python byte-policy preimage is
never weaker than the runtime limit. Adversarial quote/backslash/control-byte
tests compare the Lua upper bound with Python's canonical JSON bytes.

Caps are checked before lazy payload construction wherever possible. Disabled,
wrong-phase, and already-capped calls avoid expensive board/effect extraction.
The final serializer refuses a bundle over its configured persisted-byte cap,
and the parser also applies a non-configurable 64 MiB hard ceiling before
trusting configuration from the input.

## Side-band persistence

A deployed Lua integration must write untrusted bounded raw checkpoints
separate from state/command/ACK. The controller first consumes an immutable,
content-addressed arm packet. Offline Python validation/canonicalization then
requires the externally recorded arm and raw SHA-256 values and publishes an
immutable final bundle:

```text
itb_observatory_arm_<capture_id>_<checkpoint_seq>_<sha256>.json
itb_observatory_trace_<capture_id>_<checkpoint_seq>.raw
itb_observatory_trace_<capture_id>_<checkpoint_seq>.raw.tmp
itb_observatory_trace_<capture_id>_<checkpoint_seq>_<sha256>.json
```

Buffer events in memory and flush a bounded bundle atomically at a controlled
turn boundary or explicit experiment checkpoint. Do not append synchronously on
each RNG or scoring call. Raw game output belongs in the isolated bridge
directory; finalized offline evidence defaults under the configured artifact
root at `observatory/traces`, never beside live state/CMD/ACK files. Final
readers ignore raw/temp/publishing candidates, require the exact capture,
checkpoint, and externally trusted content SHA-256 (never guess "latest"), cap
bytes before parsing, use strict UTF-8, reject symlinks and nested paths, and
verify the opened file descriptor and directory entry remained the same and
stable across the bounded read.

The arm packet carries the authoritative build identity, checkpoint sequence,
exact manifest, trusted digests, policy, and hook plan. Its digest remains
external rather than being embedded circularly. The raw checkpoint repeats the
checkpoint sequence and records the actual successful activation time as
`started_epoch`. Finalization rederives the packet, compares raw configuration
and coverage exactly, recomputes canonical event bytes, and rejects any hook
restore conflict, filtered event, or nonempty runtime stop reason. A stopped
capture is bounded diagnostic output, not authoritative evidence, because the
schema-v2 summary cannot preserve every runtime-stop semantic without making a
complete capture look truncated or vice versa.

Final publication is create-only, content-addressed, fsynced, and made
read-only; it never replaces prior evidence. The filename digest and trusted
digest are both checked against the bytes, so later in-place mutation fails
closed.

The build identity, capture identity, exact hook-coverage manifest, checkpoint,
and cap configuration are part of the bundle. Every event family must have a
coverage entry marked `installed`, `unavailable`, or `disabled`; absence cannot
be mistaken for a negative result. Duplicate JSON keys, unknown object fields,
malformed event payloads, missing identity, non-contiguous sequence,
out-of-policy phase, cap violation, inconsistent attempted-call counts, or an
inconsistent summary fail validation.

Example offline validation:

```bash
python scripts/itb_trace.py build-arm \
  --inventory INVENTORY.json \
  --capture-identity CAPTURE_IDENTITY.json \
  --controller-artifact CONTROLLER_BUNDLE \
  --installed-modloader DEPLOYED_MODLOADER.lua \
  --config TRACE_CONFIG.json \
  --hook-plan HOOK_PLAN.json \
  --max-attempts 512 \
  --checkpoint-seq 0 \
  --output-root ARM_DIRECTORY
python scripts/itb_trace.py finalize-raw RAW_DIRECTORY/itb_observatory_trace_CAPTURE_0.raw \
  --inventory INVENTORY.json \
  --capture-identity CAPTURE_IDENTITY.json \
  --controller-artifact CONTROLLER_BUNDLE \
  --installed-modloader DEPLOYED_MODLOADER.lua \
  --arm ARM_DIRECTORY/itb_observatory_arm_CAPTURE_0_SHA.json \
  --arm-root ARM_DIRECTORY \
  --arm-sha256 TRUSTED_ARM_SHA256 \
  --raw-root RAW_DIRECTORY \
  --raw-sha256 TRUSTED_RAW_SHA256 \
  --checkpoint-seq 0 \
  --output-root FINAL_DIRECTORY
python scripts/itb_trace.py validate TRACE.json \
  --inventory INVENTORY.json \
  --capture-identity CAPTURE_IDENTITY.json \
  --trace-sha256 TRUSTED_FINAL_SHA256
python scripts/itb_trace.py summary TRACE.json \
  --inventory INVENTORY.json \
  --capture-identity CAPTURE_IDENTITY.json \
  --trace-sha256 TRUSTED_FINAL_SHA256
```

## Hooking sequence

Before any Lua change:

1. Inventory the exact clean game and active Mod Loader/bridge files. Reject
   missing build evidence or any hash mismatch.
2. Confirm there is no achievement session that a restart or timing change can
   disturb.
3. Create a separate short-lived, one-shot arm manifest bound to the exact
   build, controller/Mod Loader hashes, mission/turn, timeline/seed
   fingerprints, phase, exact config digest, caps, nonce, and expiry. A generic
   bridge command must never activate tracing.
4. Add one event family at a time, beginning with `random_int`/`random_bool`,
   only after the exact boundary is proven non-yielding and return-preserving in
   a Lua 5.1-compatible harness.
5. Use a controlled synthetic experiment, not an achievement run.
6. Compare enabled versus disabled outcomes and repeated identical trials.
7. Finalize raw evidence offline, preserve the hook-coverage manifest, and
   remove or disable the hook after capture.

Enemy methods need extra care. Base `Skill` wrappers do not automatically
observe every subclass override, and rebinding every table method can change
identity or lookup behavior. Enumerate the exact loaded functions, wrap only
known function values, and record which definitions were covered. Final action
selection may require a narrower native/Lua orchestration anchor; a post-turn
board snapshot is not proof of the candidate tournament that selected it.

## Open questions

- Which exact Lua registration boundary owns `random_int`/`random_bool` on the
  Windows build?
- Can candidate enumeration be observed without intercepting native
  pathfinding?
- Which subclass `GetTargetScore` overrides bypass a base wrapper?
- What primitive `SkillEffect` summary is sufficient for Rust conformance
  without walking engine userdata recursively?
- At what boundary can the final selected action be logged before execution?

These are explicitly unresolved. The codec makes future answers comparable; it
does not claim the hooks are already safe or complete.
