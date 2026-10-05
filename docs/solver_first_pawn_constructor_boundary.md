# Pawn constructor ownership and input boundary

October 4, 2026. Source baseline: `8968c76f` on `main`; Windows build
13725832, installed Mod Loader overlay, simulator 413. This source-only tranche
answers which original owner must construct the actor for the H8-to-G8 Move
scenario. The [normalized receipt](../data/solver_first/s1_pawn_constructor_boundary_20261004.json)
pins the executable, archive, original body ranges and stock inputs. No original
constructor, resource loader or action was executed in this tranche. S1 and all
seven acceptance gates remain open.

## Corrected ownership route

The earlier component-only proposal cannot preserve Pawn semantics. Original
inherited manager constructor `0x00226f00` installs base-manager vtable
`0x0082e184` at `0x00226f31`. Its death virtual always returns false; its class
and sound virtuals return empty strings. Original Skill append `0x00227110`
uses those virtuals, so this changes both eligibility and appended Skill data.
Genuine Pawn constructor `0x0022a920` restores Pawn vtable `0x0082e320` at
`0x0022a9bf`. Component ownership alone supplies no positive Pawn query proof.
The bounded base and Pawn vtable windows contain 10 and 13 slots respectively;
the Pawn window excludes the following string bytes.

Factory `0x00245070` takes team 1 and an owned 24-byte `PunchMech` name, allocates
the actual `0x1328`-byte Pawn, calls the complete constructor, constructs Move
using that Pawn's context/tag addresses, appends its shared owner and returns
the actual Pawn pointer. Both factory and constructor return with 28 bytes of
callee stack cleanup. The factory receiver is a Pawn-pointer vector header;
that vector alone does not establish Board membership.

The constructor's UID comes from incrementing counter `0x00894d64`, then
`0x00228b70` propagates it to manager and Skill owners. A separate CRT random
call supplies Pawn field `+0x924`. Counter initialization and lifecycle remain
open. Manager context `+0x3c` and Pawn Board owner `+0x944` are distinct fields.
No host vtable restoration, pointer transplant, guessed UID or final query
result is an admitted substitute for their original producers.

The stock definition implies HP 3, MoveSpeed 3 and Massive. Those remain source
expectations until actual construction is graded. Constructor output is
initially inactive, off-grid and nonmech, with Repair and subsequently appended
Move. The factory does not equip `Prime_Punchmech`. Equipment, placement,
registration, activation and session confirmation require separate original
producers before ordinary action legality can be claimed.

## Finite required inputs and remaining services

The first previously omitted named input is `Guarding` at constructor call
`0x0022aa4b`. Full construction also reaches Supply, OnFire, Blocking, Acid,
Radio, UnitRift, Mech_TimeTravel, Pilot_Blink, three emitters and the Artificial
Pilot. Empty portrait and ability strings do not permit omitting the genuine
Pilot: native code derives portrait names and constructs two ability records.
The receipt pins 39 stock slices from eight whole files, including inheritance,
Pilot defaults, value lookup, animations and emitters. Original body pins cover
84 distinct entries across the bounded source packets; this count is neither
whole-game coverage nor original execution.

There are 28 requested image keys. The pinned archive contains 26; exact loose
paths and the archive omit `combat/particle_boost.png` and
`portraits/pilots/Pilot_Artificial_glare.png`. Their actual native missing-resource
and fallback behavior remains unacquired. All 26 present images have independent
RGBA8 references, matched byte-for-byte by separate scalar PNG filter reversal.
These checks establish reference input identity, not native resource outputs.
The first reference builder's metadata failure is retained; the successful
builder wrote to a fresh directory.

These images use ordinary resource routes, not the player palette expansion.
Source inference identifies four outline-domain icons and 22 other present
keys; actual regex predicates remain unexecuted. Original `0x000c0eb0` can crop
and outline resource outputs, so raw PNG dimensions alone are not a complete
grade. Original `0x000bee20` directly uploads ordinary pixels, with a separate
conditional grayscale CPU-copy branch. It reaches graphics callsites beyond
the earlier `0x0009a2c0` provider, including genuine `glTexParameterf` calls.
Those services need exact caller, IAT, stack, argument and readback checks.
Stock shield offsets must be loaded with the genuine Point binding; an empty
Location table cannot stand in for those eight assignments.

The time-travel image has 943,616 RGBA bytes and 943,810 filtered scanline bytes.
Original inflate grows from `0x4000` by doubling, requiring at least a 1 MiB
capacity. Its `HeapReAlloc` call at `0x003894d6` through IAT `0x003d6214` needs
an actual bounded ownership-preserving service. The previous exclusive
1 MiB per-request limit does not cover that request. No allocator change was
made. A conditional all-26 decode-plus-CPU-copy composition requires at least
4,686,561 distinct buffer bytes under the prior monotonic no-reuse policy.
That composition is not established for every factory resource: the exact
factory budget and peak live memory remain uncertified.

## Exit and next solver join

The tranche removes an unsafe ownership assumption and inventories the concrete
inputs needed before a fresh factory acquisition. Original resource/factory/action
attempted, admitted, passed, failed and excluded counts are all zero. Independent
PNG references: 28 requested, 26 present and matched, zero mismatches, two absent
and unreplaced. No new Rust replay, simulator change, fair-input admission,
search certificate, held-out result, practical strength measurement or ledger/gate
promotion follows.

The next acquisition must close these finite input/services first, then grade
one fresh factory world: actual return and stack, Pawn vtable, Move/Repair
ownership, UID/context consistency, Pilot/status/resources and final Lua stack.
It must preserve failure evidence and supplied boundaries. Constructor ownership
then leads to guarded selection, Move consumption, repeated-Move rejection,
retained Use legality and queue settlement; enemy/environment/spawn continuity
into a ready decision state remains the S1 exit. Hidden oracle inputs stay
outside the planner. Continue on this named integration blocker; avoid counting
resource checks as new supported tactical decisions.
