# Original Ground N2 route continuation

Date: 2026-10-03. This tranche closes the original route installer/pump dependency
for the supplied Massive pawn's **H8 → G8 Water** scenario. Original `GetPath`,
vector cloning, origin stripping, pending-route copying, normal Ground animation,
coordinate/membership transfer, final arrival, route popping and input-clone
destruction now return in one continuous guest. The installed Rust replay agrees
on the conditional endpoint and HP projection. Loaded Move/action admission and
the complete tactical loop remain open; no whole acceptance gate is promoted.

The [final frozen native report](../data/solver_first/s1_ground_step_20261003.json)
records one world attempted/admitted/matched, zero failed/excluded, **89 original
calls / 877,159 instructions**, 341 verified EXE source owners/windows and 13,972
observed DLL instruction points. It reuses the exact earlier frozen Point/cache/
Dust DLL map, SHA256 `952c1b3e6ff35f09e93f4dfad82f5b44fadb05a2590dd4eef8dd54d3233e6e38`.
These are source-admission and acquisition counts, not gameplay coverage.

## Continuous route and ownership

The joined [Point/resource/cache world](solver_first_cache_point_emitter.md)
stays alive during the continuation. Its acquisition API now accepts an explicit
machine type and continuation before the actual host graphics cleanup; the
default constructor-only path is unchanged. A separate supplied Board/Pawn/
definition/pilot fixture at guest `0x11000000` avoids overlapping the existing
Lua/cache scratch world. Unspecified mapped fixture bytes are zero. Full Board,
Pawn, game/type startup and mission biome selection are excluded.

Complete original initializer `0x2fb0` supplies the movement DIR table at
`0x8cc608`. The query initializer `0x3030` supplies a different table. Original
string constructor `0x7e10` takes the pinned stock grass literal and constructs
the actual 24-byte global MSVC string at `0x8d68bc`. Original substitution produces
the heap-owned `Emitter_tiles_grass` name; no final emitter name is host-supplied.
This is a caller-selected grass world, excluding the full tileset setter/loading.

Original `0x1742d0` returns the actual two-point H8/G8 query vector. Original
`0x9a8e0` constructs a disjoint owned clone. The root call to `0x235f00` uses a
supplied by-value vector frame and origin-match flag. The installer strips H8 and
**copies** G8 into separately allocated pending storage. The original clone is
freed only after the original pump returns. Final checks retain the exact initial
query header and both query Points, prove the query/pending owners remain live,
prove the clone was freed, and check the pending copied G8 bytes even after its
logical range empties. Pending-vector transfer is not falsely described as a steal.

The original grounded step reaches `0x235cf0`, its normal emitter path, coordinate
writer `0x230320`, Board membership transfer, final-arrival `0x162140` and route
pop. The pawn ends at G8 with HP3; H8 has zero occupants, G8 has exactly the original
Pawn pointer, and the pending route is empty. The supplied pawn's stored active
and `bMoved` bytes stay **zero**. Direct installer success therefore proves neither
available Move admission nor the complete action's readiness mutation.

The original audio-disabled BSS gate remains in effect. Enabled audio startup and
callbacks are excluded; no callback-success stub bypasses the route or arrival.

## Native CRT and RNG dependency

The first retained Ground attempt stopped at native particle randomness, before
relocation. The completed acquisition executes the original initialization chain:

1. `0x39172a`: fill all 32 encoded-NULL export-cache slots, retaining the original
   PE cookie `0xbb40e64e`.
2. `0x388b84`: initialize 13 critical sections.
3. `0x38cdde`: install the original C locale with native reference updates.
4. `0x38ee3b`: allocate/store the FLS index and run native calloc/PTD construction.

The [source boundary](../data/solver_first/s1_ground_step_boundary.json) pins 50
complete source bodies, five explicitly admitted initializer spans, raw data/
constant/string identities, exact IAT and dynamic-export call frames, and stock
script slices. Atlas-omitted initializer spans remain explicit windows, without
invented atlas ownership. Native resolvers execute; their external services admit
only pinned module aliases and export names. The lock resolver uses indices 8/18
(`synch`/kernel32), while the FLS resolver uses 2/18 (`fibers`/kernel32).

Win32 module, heap, critical-section, FLS and last-error services are supplied for
one thread/active fiber under a successful FLS-present profile. Unknown imports,
callers, arguments and names fail closed. Native calloc requests exactly 868
zeroed bytes via the explicit `HeapAlloc(flags=8)` seam. The native constructor
writes seed1 at PTD+`0x18`; original `rand` performs every state recurrence and
sample calculation. No host RNG result or seed update replaces that code.

FLS-success last-error preservation is an explicit service premise.
[Microsoft's FLS documentation](https://learn.microsoft.com/en-us/windows/win32/api/fibersapi/nf-fibersapi-flsgetvalue)
does not specify successful-call clearing. Native getptd independently saves and
restores last-error. Initialization/final platform snapshots are independent
copies, and all 13 final lock recursion counts are zero.

Fresh default seed1 is privileged validation-oracle state, excluding historical
live-game RNG and fair planner inputs. Full kernel32/CRT startup, thread/fiber
switching, allocation/module/slot failure paths and CRT shutdown remain excluded.
The PTD, FLS slot/callback, two acquired module references and critical sections
remain owned; no guest teardown is claimed.

## Source-graded normal grass burst

The native origin emitter executes **15 particle calls and 120 RNG draws**, eight
per particle in the independently reviewed source order. The image-index draw
is consumed despite modulus1; an optional byte-guarded draw is absent. Every
observed seed/result agrees with the native DWORD recurrence, and consumed state
is retained: final seed `3229646617`. The Tile emitter append occurs after all
120 draws. Native origin offsets end at (-10,25) and the burst byte resets to zero.

The grader checks position, zero status/acceleration cells, lifespan, rotation,
rotation speed, image index and live flags for slots0–14, including explicit
float32 rounding and signed zero. It checks all source-initialized cells in the
17 untouched rows, the owned 1,408-byte particle extent, grass resource association
and origin Tile emitter-vector ownership. Active velocity/trig semantics, padding
bytes29–31, later evolution and rendering remain ungraded.

Heap/Lua ownership replay retains **466 allocations / 34,014 requested bytes**.
The 768 Lua callbacks and native heap events are private evidence. Actual host
textures/context/DC/window cleanup succeeds separately. Retained guest graphics
handles are unusable afterward; saved worlds cannot resume native execution.

## Rust comparison and attempt accounting

The [Rust comparison](../data/solver_first/s1_ground_step_Rust_20261003.json)
runs in a fresh separate process using simulator413 and installed-extension SHA256
`f3dfe1c3cb1aacea28abe654419c76ca7c1353afc998e4087c3b6ec86483c674`.
One conditional endpoint/HP comparison is attempted/admitted/matched, zero
failed/excluded. The Rust corridor observation contains no native RNG/PTD state.
Rust starts with an available-action observation, while the supplied native pawn's
stored active byte is zero: readiness, complete legality and action-event parity
are explicitly outside this comparison. It does not promote this family into a
fair or held-out action corpus.

The [attempt manifest](../data/solver_first/s1_ground_step_attempts_20261003.json)
retains six fresh original worlds: two failed and four completed bounded
projections with different grading. Failures are the first unresolved CRT import
and the omitted source synch alias. Prototype03 first proves the continuous route;
frozen01 adds stronger particle/query ownership grading; frozen02 persists
initial query/target Pawn/readiness fields, proves append-after-RNG order and fixes
signed-zero expected arithmetic. Final frozen03 repeats the same strong projection after removing a trailing blank
line; its source AST equals frozen02. The acquired frozen02 source was snapshotted
before that edit. Frozen01 source was reconstructed by reversing known edits and
verified against its acquired LF hash. All earlier reports/worlds and three separate
Rust comparisons remain privately retained. Source-only packets are not native
worlds; Rust replays are not additional original worlds. Earlier 14-world cache
accounting remains distinct.

The earlier cache-prefix source LF SHA `c52d077f…` remains recoverable at commit
`b429301f20d7a87f8ea54547e023ab3f1e9d7230` and in an exact private snapshot. Historical
receipts keep their acquired source identities; current-source frozen03 pins the
optional continuation API and the final new runner. No historical evidence is
silently relabeled against changed source.

## Solver-first progress and next exit

| Required report field | Result |
| --- | --- |
| Build / solver / corpus / information / objective | Build13725832, original EXE/DLL/archive and exact installed stock slices pinned, owner overlay retained; baseline `84c186ae440163056c5c39b9aea9c20e6f49983e`, simulator413; `s1-original-joined-ground-N2-development-v1`; supplied offline oracle; conditional route/ownership/RNG and endpoint/HP objectives. |
| Named blocker and reachable scenario | Normal Ground N2 H8→Water G8 for Massive pawn; native biome substitution and CRT particle randomness prevented continuous route return. |
| Before → after | Constructor dependencies returned separately → continuous original installer/pump/arrival/clone destruction returns, with membership/ownership/RNG projections and matched conditional Rust endpoint/HP. |
| Original evidence / supplied boundaries | Bounded pinned original-body execution plus independently reviewed source expectations; supplied platform services, relocated fixture, caller-selected grass, initialized type-guard epoch and installer frame. |
| Differential counts | Final native world1/1/1/0/0 and Rust endpoint projection1/1/1/0/0 (attempted/admitted/matched/failed/excluded). Six acquisition worlds separately accounted; components share each world. Complete action/full-turn admissions0. |
| Search status / bounds | Not evaluated; no certificate or valid bound. |
| Held-out / baseline latency and memory | Not evaluated. Acquisition counts/timing/retained guest bytes are not planner performance measurements. |
| Uncertainty / regressions / exclusions | No simulator change or new mismatch in the conditional projection. Full Move legality/readiness, N3 and status/item controls, velocity/evolution, audio-enabled services, enemy/environment/spawn, undo/save and mission continuation remain open. |
| Next milestone / rationale | Continue to genuine loaded Move skill/target/effect/dispatcher admission, then extended route controls and the next decision state. This tranche removed a reachable continuous-route blocker; rendering recreation remains deferred. |

Source review also corrects the pending loaded Move dispatcher frame to an owned
124-byte SkillEffect plus a separate four-byte flag. Genuine Move/Repair Skill
construction and Lua/Board/Pawn bindings, owner/stat lookup and dispatch context
are the next acquisition work. The existing Rust model/planner remains the starting
implementation; no Rust semantic change, simulator bump or broad rebuild is
needed for this tooling tranche. S1 and all seven whole gates remain open.
