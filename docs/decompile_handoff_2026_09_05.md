# September 5 decompilation handoff

The timed afternoon pass worked on the explicitly authorized
`codex/full-decompile` branch. Its implementation checkpoints run from
`7b2ac869` through `7196090a`, following `530721e2`. All 15 checkpoints were
pushed. This document records the next concrete work; it does not declare the
game fully decompiled or promote the global function-accounting ledger.

## Completed boundaries

- Assertion import handoff, measured x86 Windows SDK exception layout,
  conditional import arguments and return tails, and the composed 315-byte,
  78-node assertion owner contract. See [owner composition](native_owner_composition.md).
- Conditional feature dispatch, fallback global stores and return chain,
  joined into the 251-byte, 56-node failure frontier. One interrupt node is
  a stop boundary. Actual imported API behavior remains a premise where stated.
  See [failure composition](native_failure_composition.md).
- Lua class marker: 84 bytes/32 nodes and 576 graph cases. A separately built
  official Lua 5.1.5 x86 reference experiment supplies 70 measured cases.
  See [marker semantics](native_lua_class_marker_semantics.md) and
  [reference experiment](lua51_marker_reference.md).
- Filtered assignment: 180 bytes/71 nodes and 2,560 graph cases, plus 48
  separately measured Lua reference cases. Reserved keys, ordinary assignment
  requests, metamethod effects and protected errors are distinguished.
  See [assignment semantics](native_lua_filtered_assignment_semantics.md).
- Vector append: 95 bytes/36 nodes, 416 graph cases and 144 exact-byte Unicorn
  replays. There are 32 summarized growth calls in the replay; no actual growth
  helper execution. See [append specification](native_lua_class_vector_append.md).
- Lua reference join: 98 normal comparisons, with 20 protected errors excluded
  from normal contracts. This projects selected observations; it does not
  establish installed DLL equivalence, native register equivalence or Lua
  iteration order. See [reference contracts](native_lua_helper_reference_contracts.md).
- Call-free iterator: 79 bytes/31 nodes, independent inorder specification and
  672 graph cases under finite, consistent, disjoint tree-storage premises.
  See [successor specification](native_lua_tree_successor_semantics.md).

## Validation already completed

- Assertion-helper and SDK suite: **1,181 passed, 22 gated skips**.
- Broader Lua suite before the final join and iterator additions:
  **357 passed, 7 gated skips**.
- Reference join focused suite: **13 passed**.
- Iterator focused suite: **19 passed**, including exact-executable CLI rebuild.
- Earlier focused runs exercised the gated exact PE, Unicorn replay and fresh
  x86 Lua compilation checks. Append: **51 passed**; filtered assignment plus
  both reference suites: **163 passed**. Counts overlap; do not add them into a
  unique-test total.
- Independent semantic reviews passed for the important tranches. Public
  receipts contain normalized evidence; native binaries, raw analysis, compiler
  outputs and third-party source archives remain private working inputs.

## Next implementation

The remaining owner at RVA `0x002eb140` has this partition:

| Region | Bytes / nodes | Current boundary |
| --- | --- | --- |
| `[0x002eb140,0x002eb1bb)` | 123 / 41 | Prefix and insertion composition open |
| `[0x002eb1bb,0x002eb21a)` | 95 / 36 | Append proof, conditional growth summary |
| `[0x002eb21a,0x002eb22d)` | 19 / 10 | Epilogue composition open |

Start by composing the now-specified iterator `0x0006df30` with the prefix,
then investigate insertion `0x002e81f0`. Source/destination aliasing can permit
insertion to change the traversed topology. A whole-prefix contract needs
explicit finite traversal, result-slot and value-read lifetime premises.
The assertion call at `0x00379cc2` when the argument's second word is zero
does not itself establish nonreturn; the later reread and dereference still
need a valid-state premise if that call returns.

Growth at `0x002eb620` remains 94 bytes/40 nodes of actual behavior to replace
the tested summaries. Its child `0x002eb680` is 101 bytes/46 nodes with three
nested calls. Static RET4 evidence alone is not an allocator contract.

For the owner epilogue, let F be its frame pointer. It restores EDI, ESI and
EBX, derives ECX from `[F-4] xor F`, and calls checker `0x003574ca` from
`0x002eb222`. Under cookie equality and a normal checker return, the owner
restores EBP from `[F]`, returns to `[F+4]`, and finishes with ESP = F+12.
The mismatch path needs a **new** caller/frame/continuation join. Its checker
CALL pushes the continuation at image-base + `0x002eb227` at F-24, overwriting
the already-popped saved-EBX slot. The earlier assertion-owner failure
composition embeds continuation `0x00379e5f` and different frame relationships;
do not reuse that composition unchanged.

## Reproduction and workspace

Exact PE input remains the locally installed `Breach.exe`, SHA256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Set `ITB_EXACT_EXE` to its path for gated subprocess tests. Set
`PYTHONPATH=.local_decompile/fill_runtime` for the private Unicorn 2.1.4
installation. Set `ITB_LUA51_REFERENCE_ARCHIVE` to
`.local_decompile/lua51_reference/lua-5.1.5.tar.gz` for fresh reference builds.
Run pytest serially. Exact Unicorn checks use subprocess CLIs to avoid the
Windows in-process pytest/faulthandler diagnostic issue.

Unrelated achievement, live-run, session, recording, command and Lightning War
test changes were preserved throughout. Do not stage or revert those changes
when resuming. `AGENTS.md` already selects `gpt-6-astra` for subagents, as the
user requested. The user's explicit branch choice overrides its default-main
rule for this decompilation work.
