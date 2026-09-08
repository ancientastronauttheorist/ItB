# September 7 decompilation handoff

This timed pass continued from `4f5ff3d5` on the explicitly authorized
`codex/full-decompile` branch. The latest implementation checkpoint is
`20eb5ab4` (attachment through black-parent return), pushed to origin.
Thirty-three implementation checkpoints follow the baseline. This document
does not declare the game fully decompiled or promote the global
function-accounting ledger.

The final 38-file regression passed at September 8, 00:53 UTC:
**1,366 passed, 58 gated skips**. Exact CLI rebuilds passed separately.
The timed pass stopped at the requested September 7, 8:00 p.m. Central
deadline (September 8, 01:00 UTC). The continuation heartbeat
`decompile-until-5-pm`, named "Decompile until 8 pm", was confirmed PAUSED
at 01:00:18 UTC. Only this documentation handoff was finalized afterward.
All 33 implementation checkpoints are pushed and independently reviewed;
the handoff and top-level links are documentation-only follow-up work.

## Completed boundaries

### Vector allocation, deallocation and resize

- Growth decision (`ff250577`): strict u32/SAR arithmetic at `0x002eb620`,
  ordinary aligned geometry separately, and an unreachable size-failure arm.
  The initial decision proof covers 33 of the 40 static sites. Later bounded
  growth joins execute resize. See [growth decision](native_lua_vector_growth.md).
- Allocation decision and return tails (`0e692dd8`, `ca452f2c`): count-to-byte
  requests at `0x0008a920`, overflow/failure frontiers, small pointer return,
  and large aligned return with stored raw pointer. Nonwrapping valid-block
  premises are separate from modular machine-pointer cases. See
  [requests](native_lua_vector_allocation.md) and
  [return tails](native_lua_vector_allocation_return.md).
- Finite retry and heap allocation (`29aa2632` through `c4ee380c`): native
  retry target `0x003574db`, thunk and wrapper, exact HeapAlloc import identity,
  normal-return transcripts, retry-flag getter and error-cell writes. API and
  handler responses remain explicit premises; no universal termination or
  actual heap execution is inferred. See [retry](native_allocation_retry.md),
  [import handoff](native_heap_allocation_handoff.md), and
  [heap protocol](native_heap_allocation_protocol.md).
- Integrated successful allocation (`fc3eec2b`) joins real nested frames and
  alignment metadata, preserving the upper-count failure distinctions. See
  [allocation composition](native_vector_allocation_composition.md).
- Deallocation guard (`0a17dbcf`), resize owner (`f6cfd285`), free protocol
  (`4a752fd0`) and deallocation return join (`ec9ebbd3`): unsigned division
  guard, stride-zero pre-fault boundary, alignment-metadata inverse, HeapFree
  and conditional error translation. Free/API/accessor effects remain supplied
  where stated. See [guard](native_vector_deallocation.md),
  [resize](native_vector_resize.md), [free](native_heap_free_protocol.md), and
  [deallocation composition](native_vector_deallocation_composition.md).

### Copy domains and successful vector joins

- Short scalar copy (`ed8f35f9`) covers lengths 0-31 and overlap in both
  directions. Feature-zero scalar/REP copy (`a5c7be07`) covers lengths 32-2048,
  alignment prefixes, DWORD REP, native tail-table reads and scalar fallbacks,
  with both feature words fixed to zero and entry DF clear. Full discontiguous
  body provenance is retained without claiming the excluded paths. See
  [short copy](native_small_copy.md) and [scalar copy](native_scalar_copy.md).
- Feature-enabled forward REP byte copy (`971a4427`) covers lengths 128-2048
  in its forward-safe domain, with the relevant feature bit set and DF clear.
  Its BT flag contract only claims defined flags. See
  [REP byte copy](native_rep_byte_copy.md).
- Short forward/backward SIMD (`a8a87edf`) and larger backward SIMD
  (`a4cd0a88`) have separate explicit feature and overlap domains. Proofs check
  all XMM registers, paired or eight-load-before-store ordering, exact read
  extents, snapshots, GPRs and defined flags. Larger backward covers 128-2048;
  remaining forward feature variants are not closed. See
  [short forward](native_short_simd_copy.md),
  [short backward](native_backward_simd_copy.md), and
  [larger backward](native_large_backward_simd_copy.md).
- Native small resize/growth/append (`aee693ec`, `06d1effd`, `25dab263`) and
  larger scalar resize/growth/append (`04b2db06`, `30f1e39b`, `373373ee`) join
  the actual descendants under successful supplied heap responses. Internal
  append arguments are relocated by element index; reads from freed old
  storage are rejected. These are bounded successful domains, not every
  allocator or copy feature combination. See
  [small resize](native_small_vector_resize.md),
  [small growth](native_small_vector_growth.md),
  [small append](native_small_vector_append.md),
  [scalar resize](native_scalar_vector_resize.md),
  [scalar growth](native_scalar_vector_growth.md), and
  [scalar append](native_scalar_vector_append.md).
- Caller-specific cookie return (`5dd58e8b`) and complete append/return suffix
  (`31643fc6`) execute through the real caller return or the excluded mismatch
  failure implementation. The tree prefix remains outside that suffix proof.
  The suffix checks 5,920 cases, split equally between returns and mismatch
  frontiers. See [return](native_lua_class_vector_return.md) and
  [suffix composition](native_lua_class_vector_suffix.md).

### First-party tree machinery

- Lower-bound leaf (`add5b5ea`): `0x002e8290`, 97 bytes/44 sites, unsigned
  NUL-byte ordering, conditional stack saves, empty-root query unread, and
  ordered versus unordered-tree claims. See [lower bound](native_tree_lower_bound.md).
- Key comparator (`8d057cda`): `0x002e76a0`, 73 bytes/30 sites, all byte-order
  outcomes and six static caller sites in the discontiguous hint owner.
  Caller behavior remains separate. See [comparator](native_tree_key_compare.md).
- Initializer (`491d0188`): `0x0007d060`, 51 bytes/25 sites, an opaque normal
  retry return and three conditional interleaved head reads/stores. Partial
  aliases and synthetic zero/wrap pointers are explicit, not harmless-null
  claims. See [initializer](native_tree_node_initializer.md).
- Successful factory (`62ef3498`): actual `0x0007cd90` and initializer/runtime
  chain through one supplied successful HeapAlloc response. A fresh 24-byte
  node receives links, header, key and payload; bytes 14-15 remain untouched.
  See [factory](native_tree_node_factory.md).
- Insertion decision (`688aa245`) joins lower-bound search and candidate
  comparison: existing keys return, construction stops before `0x002e825a`.
  Existing returns imply equality even without sorted inorder keys; global
  absence/minimum guarantees need that extra premise. See
  [decision](native_tree_insert_decision.md).
- Construction join (`73e312ab`) executes the factory and stops before hint
  CALL `0x002e826b`. Its 3,630 cases include 780 existing returns and 2,850
  construction frontiers. The new node is initialized but not linked or
  rebalanced. See [construction](native_tree_insert_construction.md).
- Predecessor (`c81b8d37`), independently reviewed and exact-tested:
  `0x00071850`, 94 bytes/38 sites, 14,400 graph cases and 4,416 native cases.
  Ordered intermediate iterator-slot writes, high sentinel bytes and both DF
  values are checked. Sentinel-to-maximum interpretation requires canonical
  sentinel metadata; decrementing begin is not claimed valid C++ behavior.
  See [predecessor](native_tree_predecessor.md).

- Attachment (`13be656a`): `0x0007d0a0` through `0x0007d0f5`, 85 bytes/35
  sites, 672 native cases. Count rejection stops before `0x0007d294`. Accepted
  fixtures update count, node parent, chosen child and conditional head
  extrema, preserving node colors/key/payload/padding. All arithmetic flags,
  both DF values and complete ancestor/tree pages are checked. This is a
  standalone prefix; balancing and the hint-owner join remain open. See
  [attachment](native_tree_attachment.md). Focused tests: **24 passed**, with
  exact CLI rebuild and independent review GO.

- Black-parent return (`20eb5ab4`): attachment joined to the parent-color check and real
  return tail, 120 bytes/48 sites across 72 native cases. It blackens the
  current root, writes the result node, restores the ancestor registers and
  returns with entry `ESP+24`. Empty-tree and single-root left/right cases
  are covered; color 255 tests the machine's nonzero branch only. Red-parent
  balancing and global red-black invariants remain open. Focused tests:
  **15 passed**, including exact CLI rebuild, with independent review GO. See
  [attachment return](native_tree_attachment_return.md).

## Validation and reproduction

The final broad run at **September 8, 00:53 UTC** was **1,366 passed and
58 gated skips across 38 files**, including the black-parent return.
The previous broad run at **September 8, 00:47 UTC** was **1,352 passed and
57 gated skips across 37 files**, including predecessor and attachment.
The earlier broad run reported at **September 8, 00:09 UTC** was **1,194 passed and
49 gated skips across 31 files**. Separate focused results reported during
integration include comparator **22 passed**, initializer **43 passed**,
insertion decision **12 passed**, construction **18 passed**, and predecessor
**47 passed**. Exact CLI rebuilds were exercised separately with the private
runtime enabled, including the predecessor's two builds. These scopes overlap;
do not sum them into a unique-test total or describe gated skips as passes.
Important semantic and replay tranches received independent read-only review.

The executable input is private:
`B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe`, SHA-256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`, image
base `0x00400000`. Exact replay pins Capstone 5.0.7 and Unicorn 2.1.4.
Raw disassembly, temporary code and runtime dependencies remain under
`.local_decompile`; the installed PE stays at its private input path. Published
receipts contain normalized
instruction evidence and hashes, not native dumps. Publication uses verified
raw hashes and exclusive creation.

For a focused exact test in PowerShell, from the repository root:

```powershell
$env:ITB_EXACT_EXE = 'B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe'
$env:PYTHONPATH = '.local_decompile/fill_runtime;.'
python -m pytest tests/test_itb_native_tree_predecessor.py -q
```

Run exact subprocess/Unicorn tests serially. Each linked document identifies
its source receipts and CLI flags. Generally `build` emits deterministic
UTF-8/LF JSON through binary stdout, `verify` rebuilds from the exact PE, and
`verify-structure` checks immutable receipt/source seals without replay.
Published files use prefix `windows_build_13725832_31fe35265598_` under
`data/observatory/programs/`. Canonical receipt digests and encoded-file hashes
are different values; use the corresponding documented check.

## Checkout preservation

The branch remains `codex/full-decompile` by explicit user authorization,
overriding the repository's ordinary main-only policy for this task. No
branch switch, reset or cleanup of unrelated work is authorized by this
handoff. The preserved unrelated modified files are
`data/achievements_detailed.json`, `data/weapon_penalty_log.json`,
`logs/default_log.md`, `recordings/default/resist_probe.jsonl`,
`recordings/failure_db.jsonl`, `sessions/active_session.json`,
`src/loop/commands.py`, and `tests/test_lightning_war_tools.py`.
Untracked mission-board/solve/threat-audit recordings and
`run_notes/lightning_war_smoke_2026-08-29/` also remain user work. Preserve
these exactly; stage only the intended observatory tranche. The new observatory proofs and this handoff are task outputs, distinct from
that pre-existing work.

## Next exact frontier

Attachment is sealed through `0x0007d0f5`, with the bounded black-parent
path additionally joined through the real return. Next derive red-parent
balancing through the normal return preceding `0x0007d294`, then close the
remaining hint owner `0x002e8300`, whose 454-byte/165-site body is
discontiguous; do not force it through a single-span decoder. The exception
wrapper at `0x002e84e0` installs an exception frame and remains an explicit
boundary. Count-failure cleanup and exception dispatch also remain open.
Compose attachment, balancing, hint selection and exception behavior only
after their own effects and ancestor-memory joins are established.

The larger goal still includes the original class-owner prefix and its
interaction with traversal/insertion. Existing suffix, leaf and construction
proofs do not automatically establish that whole owner: tree topology may
change, result-slot/value lifetimes need protection, and exceptional paths
retain their stated frontiers. The timed pass is stopped; resume with the
precise remaining work above rather than promoting broad completion.

## Balancing preparation (analysis only)

Independent private native inspection places the call-free continuation at
`[0x0007d0f5, 0x0007d294)`: 415 bytes and 146 instruction sites. These are
planning boundaries, not a completed red-parent balancing proof. The
black-parent fast path was subsequently closed as a bounded composition.

- Black-parent fast return (now separately sealed for the selected corpus):
  `[0x0007d0f5, 0x0007d104)` plus
  `[0x0007d280, 0x0007d294)`, 35 bytes/13 sites. It blackens the current root,
  writes the new-node result and returns with `RET 20`. This path avoids the
  loop's extra ESI stack save.
- Red-uncle recoloring: `[0x0007d1c6, 0x0007d1e3)`, 29 bytes/8 sites.
- Mirrored optional triangle rotations: `[0x0007d127, 0x0007d161)` and
  `[0x0007d1e7, 0x0007d223)`, 58/23 and 60/23 bytes/sites respectively.
- Mirrored line-case recoloring and rotations:
  `[0x0007d161, 0x0007d1c0)` and `[0x0007d223, 0x0007d26f)`, 95/31 and
  76/28 bytes/sites, with the shared final parent-link store at `0x0007d26f`.
- Shared link/recheck/ESI restore: `[0x0007d26f, 0x0007d280)`, 17 bytes/5
  sites. Loop entry is `0x0007d105`; the extra save is at `0x0007d104` and
  restore at `0x0007d27f`.

Prove rotations for root and nonroot parents, both parent-child orientations,
and nil versus non-nil transferred middle subtrees. Preserve keys, payloads,
node identity, count and head extrema while updating parent links and root.
Keep the color byte at offset 12 separate from the nil byte at offset 13.
The machine contract distinguishes zero/nonzero colors; a red-black-tree
corollary should explicitly require canonical colors and the preexisting
black-height/red-parent invariants except the new local violation. Derive
loop progress from ancestry and tree height, not a replay step limit.

## Caller join to preserve next pass

The construction owner currently stops **before** CALL `0x002e826b`. With
owner entry stack pointer `O`, successful construction has already executed
its nested heap boundary at `O-96`. At the stop, `ESP=O-36`; a future hint
callee enters at `O-40`. The four prepared DWORDs at `O-36`, `O-32`, `O-28`
and `O-24` are respectively the result-slot address `O-8`, candidate node,
new node's key-field address `P+16`, and new node `P`. The key field contains
the query pointer, not the query's first DWORD. Preserve the whole ancestor
frame and key/result lifetimes when replacing the hint call boundary.

The hint owner's normalized static call partition has seven attachment calls,
six key comparisons, one predecessor, one successor, one exception wrapper
and one security-cookie check. Sealed leaf receipts establish those leaf
contracts; they do not establish which calls the hint owner chooses or the
combined tree effects. Its discontiguous ranges must retain exact static
source identity, and every call-site frame needs its own join. The
`0x002e84e0` wrapper's exception-frame installation prevents treating it as
an ordinary normal-return helper without separately proving that machinery.

The red-uncle tranche deserves a separate ordered-access oracle: after its
parent and uncle color writes, it reloads the current node's parent and that
parent's parent to select the grandparent color write, then reloads that
ancestry again to advance the current cursor. At the shared recheck it reads
the new cursor's parent and compares that parent's color. Avoid substituting
cached dispatch pointers for these fresh reads. A first bounded test can use
one recoloring followed by a black-parent exit, before adding repeated ascent
or either rotation. This observation is private native analysis for the next
proof; no new recoloring conformance is asserted here.

A minimal canonical corpus for that next recoloring join starts with a black
root and two red children, each with sentinel children. Attach a fresh red
leaf into each of the four available child positions in turn. The opposite
red child supplies the red uncle, so the loop should recolor both old
children black, temporarily recolor the old root red, ascend to it, exit on
the black sentinel parent, and blacken the root before returning. Check the
count change from three to four and the orientation-dependent head extrema
alongside full ordered accesses, saved ESI, result storage and node padding.
This gives a finite canonical starting corpus without claiming the mirrored
rotations or a general loop theorem.
