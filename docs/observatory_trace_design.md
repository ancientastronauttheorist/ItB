# ITB Engine Observatory trace contract

## Status and safety boundary

This document defines a trace evidence contract and the smallest future Lua
integration. The reusable Python codec is implemented in
`src/observatory/trace_codec.py`; it has no dependency on the live bridge.

No trace hook is installed by this work. `src/bridge/modloader.lua`, the
installed game, the game process, and the active achievement session remain
untouched. Deployment requires a separately reviewed safe window.

## Goals

The trace must answer narrow fidelity questions without becoming part of game
behavior. Initial event families are:

- `random_int` and `random_bool`: raw arguments, result, call-site tag,
  sequence. The `random_bool` argument is deliberately named `argument`; calls
  such as `random_bool(5)` do not establish percentage semantics.
- `enemy_candidate`: pawn, skill, origin, destination, target, enumeration
  order.
- `enemy_target_score` and `score_positioning`: candidate identity and score.
- `get_target_area` and `get_skill_effect`: primitive summaries of inputs and
  returned areas/effects.
- `enemy_action_selected`: final pawn movement, skill, and target selected by
  the engine.

Every bundle carries the build platform, architecture, executable hash,
numeric build/depot identity plus its evidence source, and scripts/maps
revisions. Hashes are lowercase SHA-256 values. The architecture vocabulary
matches the inventory schema, including ARMv7 and a canonical list of slices
for universal Mach-O builds. Unknown architecture is explicit rather than
guessed; unavailable build evidence requires null build/manifest fields.
Evidence from different identities must not be pooled silently.

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

For proven non-yieldable Lua 5.1 functions, a wrapper can preserve multiple
returns with a
`pack(...)= {n=select("#", ...), ...}` helper and
`unpack(results, 1, results.n)`. The direct `pack(original(...))` call preserves
the original error path while guaranteeing one invocation. This pattern must
not be applied generically to functions that may yield: Lua 5.1 yield behavior
across C/Lua wrapper boundaries requires separate proof, and an unsafe wrapper
must not be installed.

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
- truncation and dropped/error counters.

Caps are checked before lazy payload construction wherever possible. Disabled,
wrong-phase, and already-capped calls avoid expensive board/effect extraction.
The final serializer refuses a bundle over its configured persisted-byte cap,
and the parser also applies a non-configurable 64 MiB hard ceiling before
trusting configuration from the input.

## Side-band persistence

A future Lua implementation should use files separate from state/command/ACK:

```text
itb_observatory_trace.json
itb_observatory_trace.json.tmp
```

Buffer events in memory and flush a bounded bundle atomically at a controlled
turn boundary or explicit experiment checkpoint. Do not append synchronously
on each RNG or scoring call. Readers must select only a complete valid bundle
and tolerate a partial/malformed temp candidate without writing back.

The build identity and cap configuration are part of the bundle. Duplicate JSON
keys, unknown object fields, malformed event payloads, missing identity,
non-contiguous sequence, out-of-policy phase, cap violation, or inconsistent
summary fail validation.

## Hooking sequence

Before any Lua change:

1. Inventory the exact clean game and active Mod Loader/bridge files.
2. Confirm there is no achievement session that a restart or timing change can
   disturb.
3. Add one event family at a time, beginning with `random_int`/`random_bool`.
4. Use a controlled synthetic experiment, not an achievement run.
5. Compare enabled versus disabled outcomes and repeated identical trials.
6. Remove or disable the hook after evidence capture.

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
