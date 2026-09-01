# Native Lua registration bootstrap survey

Status: promoted to an exact executable-rebuilt artifact. This document retains
the research interpretation and boundaries for one native Lua bootstrap path;
`windows_build_13725832_31fe35265598_native_lua_cclosure_gc_metatable_consumers.json`
is the normalized evidence. Neither is a source reconstruction.

## Bound executable and prerequisites

The observations below apply only to:

- `Breach.exe`, Windows build `13725832`, x86 PE, SHA-256
  `31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
- Program-facts atlas
  `windows_build_13725832_31fe35265598_program_facts.json`, canonical SHA-256
  `631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803`.
- Direct-Lua-call census
  `windows_build_13725832_31fe35265598_native_lua_direct_call_census.json`,
  canonical SHA-256
  `07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608`.
- Closure table-key provenance census
  `windows_build_13725832_31fe35265598_native_lua_cclosure_table_key_provenance.json`,
  canonical SHA-256
  `8b8cab571c3c8945dae440933107022b35eed28b4c806a35188202bd52073db6`.
- Direct `lua_setfield` closure-publication census
  `windows_build_13725832_31fe35265598_native_lua_cclosure_setfield_publications.json`,
  canonical SHA-256
  `b9a77c1e5e37f251f44b4c1fac304ddbea5251c1cad164e0538c4970417608a6`.
- Direct table-setter and staged-indirect publication censuses, which the
  table-key verifier recursively exact-rebuilds before this artifact is
  accepted.
- Promoted GC metatable-consumer artifact, pretty-printed file SHA-256
  `9d4435d6d67b5ab46b6391585fecb1e09dc3be926dac66aa04fa1b4c39e34fc7`
  and canonical JSON SHA-256
  `4c2e4be756ef611f234d7d78418daf3fe16be2928ef440bb67b5a586df3bef8a`.

All addresses in this note are image-relative RVAs. Lua API interpretations
use the Lua 5.1 ABI: `LUA_REGISTRYINDEX == -10000`, table setters consume their
key/value or value operands, and `lua_setmetatable` consumes the table at the
top of the Lua VM stack. `lua_gettable` and `lua_settable` may honor
metamethods; `lua_rawget` and `lua_rawset` do not. These are ABI premises, not
claims about a particular runtime invocation.

## Native bootstrap edge

The Ghidra-declared direct-call relation contains one incoming edge to the
registration constructor:

```text
0x0004caa0  -- direct CALL at 0x0004cade -->  0x002e6900
```

Within the one 114-byte atlas range for `0x0004caa0`, the relevant static
fallthrough sequence is:

1. `luaL_newstate` at `0x0004cab0` is conditionally reached when the stored
   state field is zero.
2. `luaL_openlibs` is called at `0x0004cad2` with the stored state.
3. `mov ecx,[esi+0x10]` at `0x0004cad8` is followed by the cdecl cleanup
   `add esp,0xc` at `0x0004cadb`, then by the direct call to `0x002e6900` at
   `0x0004cade`. The cleanup does not overwrite `ecx`.

That proves a static native call edge and local instruction order only. It does
not prove the state allocation succeeded, that either Lua call returned
normally, that this function executes, or that it is the sole startup path.

## Registry lookup and four construction/store chains

`0x002e6900` first probes `LUA_REGISTRYINDEX["__luabind_classes"]`:

| fact | RVA |
| --- | --- |
| key push | `0x002e698f` |
| staged `lua_pushstring` call | `0x002e6995` |
| registry-index push | `0x002e6997` |
| `lua_gettable` call | `0x002e699d` |
| `lua_touserdata` call | `0x002e69a6` |
| null-result test / branch | `0x002e69ba` / `0x002e69bc` |

The `jne` target from that test skips all four chains. Consequently, the
following table describes the exact fallthrough arm after a null
`lua_touserdata` result; it does **not** establish that the initial registry
lookup was absent, that a stored item has any particular dynamic type, or that
the arm ran.

| registry key (literal RVA; NUL-inclusive SHA-256) | key push / `lua_pushstring` | userdata size push / creator | metatable creator | `__gc` closure | metatable setter | `lua_setmetatable` | registry-index push / store |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `__luabind_classes` (`0x0043bf18`; `d9b53c957a9924e6583d6b1931dfc280dfff360c1a81042f6264b3d285d355fa`) | `0x002e69c2` / `0x002e69c8` | `0x002e69ca` (24) / `0x002e69cd` | `0x002e69d9` | `0x002e69f1` | `0x002e6a03` (`lua_settable`) | `0x002e6a08` | `0x002e6a2a` / `0x002e6a30` (`lua_settable`) |
| `__luabind_class_id_map` (`0x0042a86c`; `9ff3832e39fd8abb51ed203f64ef8a5b9c518d8f72156c942d3b99e7a056cd61`) | `0x002e6a32` / `0x002e6a38` | `0x002e6a3a` (12) / `0x002e6a3d` | `0x002e6a7b` | `0x002e6a8c` | `0x002e6a9d` (`lua_setfield`) | `0x002e6aa9` | `0x002e6aaf` / `0x002e6ab5` (`lua_settable`) |
| `__luabind_cast_graph` (`0x0043bf6c`; `2c6601dedc983c9694b1c556740cbe937c23189effa02a9d6129090e336f8800`) | `0x002e6ab7` / `0x002e6abd` | `0x002e6abf` (4) / `0x002e6ac2` | `0x002e6ae8` | `0x002e6af9` | `0x002e6b0a` (`lua_setfield`) | `0x002e6b16` | `0x002e6b1c` / `0x002e6b22` (`lua_settable`) |
| `__luabind_class_map` (`0x00420fa8`; `79d79631d86216b5e947d500c8c800cb872d14004794f546f7099c0c4c451183`) | `0x002e6b24` / `0x002e6b2a` | `0x002e6b2c` (12) / `0x002e6b2f` | `0x002e6b55` | `0x002e6b66` | `0x002e6b77` (`lua_setfield`) | `0x002e6b83` | `0x002e6b89` / `0x002e6b8f` (`lua_settable`) |

Each literal is printable ASCII plus a NUL terminator in the non-writable
`.rdata` section (`0x40000040`). The table's exact local grammar is: push the
registry key; create a userdata of the listed byte size; create a table; place
a native closure under `__gc` in that table; use the table as the userdata's
metatable; and perform a `lua_settable` with `LUA_REGISTRYINDEX` to consume the
still-live registry key and userdata. The first `__gc` insertion uses
`lua_settable`; the other three use `lua_setfield`.

In stack notation, the common normal-return prefix is
`B -> B,K -> B,K,U -> B,K,U,T`. The first chain then follows
`B,K,U,T -> B,K,U,T,G -> B,K,U,T,G,C -> B,K,U,T` through
`lua_settable(-3)`. Each later chain follows
`B,K,U,T -> B,K,U,T,C -> B,K,U,T` through `lua_setfield(-2,"__gc")`.
All four then use `lua_setmetatable(-2)` to reach `B,K,U`, followed by the
registry-index `lua_settable` that consumes `K,U` and restores `B`.

The first chain has one intervening native initializer: call `0x002e6a25` to
`0x002ebb30` occurs after `lua_setmetatable` and before the registry setter.
Its exact Lua-call tree is net-zero on the VM stack. Helpers `0x002eb990` and
`0x002eba60` each create and populate one table and consume it with
`luaL_ref`; helper `0x002ea2d0` leaves one populated table, which the parent
consumes with `luaL_ref` at `0x002ebb73`. Thus the initializer's normal-return
join still has `B,K,U`. This is a local stack-effect proof, not a claim that
the helper calls return or that their references remain valid.

The promoted artifact phrases these records as **conditional native
construction and registry-index assignment**. The four final registry writes
use `lua_settable`, not `lua_rawset`, so this note does not prove raw or durable
registry placement. It should not be phrased as ownership, class identity, a
source-level Luabind implementation, or persistence beyond the local call
grammar.

## `luabind.function` raw metatable cache and consumer

The fifth `__gc` publication belongs to a different, two-function grammar.
Helper `0x002ea4e0` uses the exact literal `luabind.function` at
`0x0043c570` (16 bytes excluding NUL; NUL-inclusive SHA-256
`151c5227a1df5d9eb41c7bb391a21b8ba42be9fa4d6a6a96f95bd9e19a25d796`).
The literal is in the same non-writable `.rdata` section (`0x40000040`).

The helper's cache lookup and miss arm are:

| fact | RVA |
| --- | --- |
| cache-key push / `lua_pushstring` | `0x002ea4ea` / `0x002ea4f0` |
| registry-index push / `lua_rawget` | `0x002ea4f2` / `0x002ea4f8` |
| `lua_type(-1)` / compare with table type 5 / hit branch | `0x002ea501` / `0x002ea50a` / `0x002ea50d` |
| miss-arm `lua_settop(-2)` | `0x002ea512` |
| metatable creator | `0x002ea51d` |
| `__gc` key push / `lua_pushstring` | `0x002ea523` / `0x002ea529` |
| `__gc` closure / callback | `0x002ea533` / `0x002ea4b0` |
| `lua_rawset(-3)` | `0x002ea53c` |
| cache-key push / `lua_pushstring` | `0x002ea542` / `0x002ea548` |
| `lua_pushvalue(-2)` | `0x002ea54d` |
| registry-index push / `lua_rawset` | `0x002ea556` / `0x002ea55c` |

Let `B` denote the caller's prior Lua VM stack, `U` its freshly allocated
userdata, `T` the metatable table, `G` the `__gc` key, `C` the native closure,
and `K` the cache key. On a cache hit, `lua_rawget` leaves `B,U,T`; the helper
checks only that the retrieved value has Lua type 5 and returns it on the
stack. On a miss, the exact normal-return trace is:

```text
B,U -> B,U,T -> B,U,T,G -> B,U,T,G,C -> B,U,T
    lua_createtable   lua_pushstring     lua_pushcclosure   lua_rawset(-3)

B,U,T -> B,U,T,K -> B,U,T,K,T -> B,U,T
          key push      lua_pushvalue(-2)  lua_rawset(LUA_REGISTRYINDEX)
```

The complete atlas contains one decoded direct call to this helper. Consumer
`0x002ea820` allocates a four-byte userdata at `0x002ea82f` and calls the helper
at `0x002ea839`. Four decoded non-call instructions follow at `0x002ea83e`,
`0x002ea841`, `0x002ea843`, and `0x002ea844`; the next Lua API call is
`lua_setmetatable(L,-2)` at `0x002ea846`. Thus, on normal return from either
helper arm, the table left by
the helper is consumed as that userdata's metatable. On the miss arm only, it
is exactly the freshly created table containing the `0x002ea4b0` `__gc`
closure; a cache hit accepts any table already present under the raw registry
key and does not revalidate its origin or contents.

The consumer then pushes a light userdata at `0x002ea852` and calls a dynamic
two-upvalue `lua_pushcclosure` at `0x002ea85e`. Its local stack transition is
`B,U,P -> B,C`: the metatable-bearing userdata and light userdata become the
two closure upvalues. `lua_pushvalue(-1)` at `0x002ea873` duplicates that
closure, `luaL_ref(L,LUA_REGISTRYINDEX)` at `0x002ea87f` consumes the duplicate,
the returned integer is stored at native holder offset `+4` at `0x002ea888`,
and `lua_settop(-2)` at `0x002ea88b` removes the remaining closure. This proves
a finite static consumer/reference chain, not its runtime lifetime or validity.

Unlike the four bootstrap registry assignments, this helper uses
`lua_rawget`/`lua_rawset`, so its local cache access bypasses registry
metamethods. That distinction does not prove that the cached table remains
unchanged, that the registry survives, or that the helper has no indirect
callers.

## Complete proved `__gc` publication partition

The direct `lua_setfield` census contributes the three `__gc` sites at
`0x002e6a8c`, `0x002e6af9`, and `0x002e6b66`. The table-key provenance census
contributes `0x002e69f1` and `0x002ea533`; its other five setter publications
use `class`, `property`, or `super`. The union therefore contains exactly five
`__gc`-keyed sites among the ten exact native immediate-C-closure setter
publications. This is a partition of that proved publication universe, not a
claim that Lua code, dynamically keyed native code, or another unrecognized
grammar cannot construct an `__gc` field. In particular, initializer helpers
`0x002eb990` and `0x002eba60` contain additional staged
`lua_pushcclosure`/`lua_rawset` `__gc` constructions outside this normalized
ten-site immediate-closure setter universe.

## `class`, `property`, and `super` consumer boundary

The current key-provenance census proves static publication under exact global
environment keys `class`, `property`, and `super`. A full atlas decode found
the following references to those particular literal addresses:

| exact literal | literal RVA | atlas references |
| --- | --- | --- |
| `class` | `0x0043bf98` | publication at `0x002e6b91` only |
| `property` | `0x0043bf8c` | publication at `0x002e6bb2` only |
| `super` | `0x0043bfa0` | publication at `0x002e6bf1`; callback-side publication/clear paths at `0x002eb068`, `0x002eb103`, `0x002eb25c`, and `0x002eb310` |

This is not a negative proof of native or Lua consumers. There are additional
file-backed exact literals for `class` (`0x00420f9f`, `0x00436d66`,
`0x00436dec`, `0x0043c52e`) and `property` (`0x00425144`), while compiled Lua,
dynamic strings, indirect/computed references, un-atlased native code, and
later mutation remain outside this scan. It therefore cannot establish
ordinary global lookup success, runtime reachability, consumer absence, or
semantic meaning for those names.

## Promoted fail-closed artifact

The build-keyed `pe_native_lua_cclosure_gc_metatable_consumers` census is
implemented in `src/observatory/native_lua_cclosure_gc_metatable_consumers.py`
and composed from the exact
atlas, Lua direct-call census, direct-setfield publication census, and
table-key provenance census. It retains exactly five `__gc`
publication/consumer records, shared guard/caller facts for the first four,
and the helper/cache/consumer facts for the fifth. The evidence also seals eight
core bodies (1,924 bytes), 667 CFG nodes / 670 edges, 61 direct and 58 staged
Lua calls, 66 semantic instruction points, 49 contiguous adjacency proofs,
five callback identities, four initializer-subtree edges, and all seven exact
atlas references to its central targets. Every record includes
only normalized RVAs, instruction size/SHA-256 facts, literal metadata/hashes,
direct-call import identities, a finite CFG edge path, and a declarative
Lua-stack trace.

Implemented exact checks:

1. Rebuild all record instruction facts from the bound PE and reject a changed
   atlas or prerequisite digest.
2. Require the declared direct edges `0x0004cade -> 0x002e6900` and
   `0x002ea839 -> 0x002ea4e0`, plus exact state-register transfer at both call
   boundaries. Retain the `luaL_newstate` / `luaL_openlibs` caller grammar as a
   separate bootstrap fact rather than a runtime-execution claim.
3. Require all five non-writable, NUL-terminated registry-key literals, the
   shared `__gc` literal, and every registry-index selector push used by an
   asserted lookup or write.
4. Prove per-chain native argument adjacency, direct/staged Lua API identity,
   CFG continuity, no alternate atlas entries into asserted dominated regions,
   and the Lua VM-stack trace through the registry store.
5. Join `__gc` closure/site facts to the existing publication artifacts rather
   than inferring them from names or source conventions.
6. Distinguish the null-result gate from a claim that a registry entry is
   missing, and make the three later bootstrap chains conditional on that same
   exact fallthrough arm.
7. Require the fifth helper's type-5 hit branch and miss-arm join to leave the
   same `B,U,T` stack shape at its consumer, and distinguish the first four
   `lua_gettable`/`lua_settable` operations from its raw registry access.

The adversarial tests mutate one fact at a time: caller edge or
fallthrough, state-register transfer, one literal byte/section
writability/hash, registry selector, userdata size, API IAT/call form, `__gc`
setter kind, metatable index, registry-store order, branch direction/gate
target, fifth-helper type constant or duplicated-table index, raw/non-raw cache
classification, predecessor/entry audit, and an invalid prerequisite canonical
digest. The CLI also refuses symlink, reparse-point, non-regular, differing,
or concurrently changed output. Structural validation may replay stored hashes,
paths, dominance, and VM traces, but instruction decoding, branch semantics, register-write
classification, and literal bytes must remain exact-PE rebuild obligations.

## Explicit nonclaims

This survey and the promoted artifact do not prove runtime execution, call
success, frequency, persistence, lifetime, global availability, cache-hit provenance, table
identity beyond the local stack grammar, registry-reference validity after
return, user-data meaning, source-level metatable ownership, source
equivalence, subsystem purpose, absence of later mutation, absence of indirect
callers, or completeness of all Lua bootstrap/consumer paths. Their entry
audits cover atlas function entries and Ghidra-declared direct targets; indirect,
exception, callback, or externally fabricated entries absent from those facts
remain outside the proof.
