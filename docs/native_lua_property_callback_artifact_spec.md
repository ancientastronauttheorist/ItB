# Native Lua `property` callback artifact specification

Status: reviewed exact-build implementation packet. This document freezes the
next normalized-artifact boundary and its acceptance criteria; it is not itself
an executable-rebuilt artifact and does not promote the surveyed behavior.

## Bound inputs

All facts are specific to the x86 Windows `Breach.exe` from build `13725832`,
SHA-256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
The implementations must recursively bind and exact-verify these prerequisites:

- program-facts atlas canonical SHA-256
  `631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803`;
- direct Lua-call census canonical SHA-256
  `07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608`;
- property-consumer artifact canonical SHA-256
  `2c6569177595cbdc8abdbe4ba1bdc3d09f4bb0d15dac5d280c16ba3dfcc2d3b9`;
- property-initializer artifact canonical SHA-256
  `b76b3d46d30da4801a3bc4f67be78d3818f847557a0b275f6048120873b44bc4`.

The initializer already seals the zero-upvalue closure producer for callback
`0x002e9f40`, the two-upvalue `[K,B]` producer for callback `0x002ea1a0`, and
the getter identity `0x002ea110` through its consumer prerequisite. A follow-on
artifact must consume those identities rather than restating producer
provenance from callback addresses alone.

## Required implementation split

Build two artifacts, in this order:

1. `pe_native_lua_property_cleanup_chain` seals callback `0x002e9f40`, helper
   `0x002e9f00`, the initializer's cleanup-closure producer, the callback's
   direct helper call, and the complete two-target/two-reference partition.
2. `pe_native_lua_property_operator_dispatch_chain` seals wrapper
   `0x002ea1a0`, recognizer `0x002ea3d0`, the initializer's wrapper-closure
   producer, the shared getter-pointer predicate, and the complete
   two-target/77-reference partition. The 76 recognizer callers remain operand
   reachability evidence only; do not classify their heterogeneous semantics.

A monolithic four-body artifact is mechanically possible but is not the
reviewed boundary. Cleanup behavior and the large recognizer caller frontier
have separate semantic and regression surfaces.

Each artifact should follow the established property-chain pattern: one
read-only builder module under `src/observatory/`, one CLI under `scripts/`, a
checked-in pretty JSON artifact under `data/observatory/programs/`, and focused
tests. The writer must refuse to overwrite a non-identical file. Structural
validation must not reopen the PE; exact validation must rebuild from the PE
through the complete prerequisite chain and byte-compare canonical evidence.

## Exact function identities

Use the existing enhanced CFG plus `writes_edi` enrichment and
`caller_entry_rva`, matching the property-consumer artifact's graph schema.
The generic hashes are retained to make the transformation auditable; the
EDI-enriched hashes are the required artifact identities.

| role | entry | bytes | body SHA-256 | atlas-record SHA-256 | nodes / edges | generic CFG SHA-256 | EDI-enriched CFG SHA-256 |
| --- | --- | ---: | --- | --- | ---: | --- | --- |
| cleanup registry helper | `0x002e9f00` | 64 | `65d5712025be3aeb9d3bec9845edf4aec64fb7aaaf04ea706b5482d8d43305eb` | `86390c564903f8df5223d60089c9b91976b494b244f5c6f10d1fe3a08eb15361` | 28 / 29 | `18d3bdf9c8cfe60cb906f2cc0b9b370709aee78ed209ac75245b51776ed7aec3` | `5078c6cb6ca9031f04531df4b21f8d9e35406601dd301f90da5e0a582d14f888` |
| cleanup callback | `0x002e9f40` | 137 | `42a2e05350e953d42a76c65c17f665e384fd53bc3ef4e1d578681a10c48008ba` | `9bfdab42775774edd1e0cb41c123ec97ac3014322e061d6576ca6a4491efc45f` | 55 / 57 | `762740bffef34640f728fe17bf8f1b43b09cfd0b8d0d9b7d22e16cf3bcaaa839` | `9296c21c4acc66e0cc63554a3fdb5dd27cf78d3b61bbf975b36a5af094a0640f` |
| operator wrapper | `0x002ea1a0` | 302 | `bea28c212b1b1b163611046a80f2c3da4c4886aaa1bea785bde455f7b0e5b9a3` | `0d0138f5cac102c6703b02a6cf0e0f52a5f18bc8aa169a531157ef1d997d6f5a` | 113 / 117 | `0b3b39079c2d631751ddce334bb86ff325386f05acf4e4cc4b92fa9e76bbe467` | `19cb92f34c9935478df596f4acf5864d08da8d54df33d125e6ee7b9c74dd98dd` |
| numeric-slot recognizer | `0x002ea3d0` | 93 | `fb64dfb22aa5813027232506af9b60f97a85e1d5b79b7d63182dc4ce957f02c0` | `4dc769bd01ae9209e2e1f18d57e3c3ac3503048927b3d919bedc85a75ec74ae2` | 42 / 42 | `f2b08365da54a333a11b1bc0bce7665b81b2f6bf3a67baa931ed6604d74652cb` | `7b3681a93f0cad3cb8f73d2a25ad7302a2295bf04199591b7d56651efb7af313` |

The cleanup pair totals 201 bytes, 83 nodes, and 86 edges. The operator pair
totals 395 bytes, 155 nodes, and 159 edges. The complete four-body packet is
596 bytes, 238 nodes, and 245 edges.

## Cleanup-chain acceptance grammar

### Direct Lua-call partition

The helper has exactly three direct `FF 15` Lua-import calls:

```text
0x002e9f17  lua_pushlightuserdata
0x002e9f1e  lua_pushnil
0x002e9f2a  lua_rawset
```

The callback has exactly seven:

```text
0x002e9f4b  lua_touserdata
0x002e9f59  lua_pushstring
0x002e9f62  lua_gettable
0x002e9f6b  lua_type
0x002e9f7b  lua_settop
0x002e9f89  lua_pushvalue
0x002e9f94  lua_call
```

No register-dispatched Lua call occurs in either body. The artifact must join
all ten sites to the direct-call census and reject any missing or additional
direct Lua call in either atlas range.

### Helper behavior

Under the observed native convention, `ECX` is the native pointer and the Lua
state is the one stack argument. `ESI` starts at zero. The unsigned count at
native offset `+0x2c` is compared with zero; `jbe` exits when it is zero. For
each byte offset `i` from zero through `count - 1`, the loop performs:

```text
lua_pushlightuserdata(L, native_pointer + i)
lua_pushnil(L)
lua_rawset(L, LUA_REGISTRYINDEX)       # LUA_REGISTRYINDEX = -10000
```

The increment at `0x002e9f30` and unsigned `jb` at `0x002e9f37` close the
loop; `ret 4` is at `0x002e9f3d`. Normalize this as a finite registry-nil loop,
not as a source-level ownership or allocation operation. Do not assign a type
or meaning to the pointer, `+0x2c` count, or lightuserdata keys.

### Callback behavior

The callback passes raw `lua_touserdata(L,1)` output through `EDI`; there is no
null check before the native tail. It pushes and indexes the exact literal:

| role | RVA | printable bytes | bytes including NUL | NUL-inclusive SHA-256 | section |
| --- | --- | ---: | ---: | --- | --- |
| lookup key `__finalize` | `0x0043c50c` | 10 | 11 | `2da9eac9965b6b70aa210a588888733805c3214ecd627e37afd1aa1909b100b7` | `.rdata`, RVA `0x003d6000`, characteristics `0x40000040`, non-writable |

`lua_gettable(L,1)` is metamethod-aware. `lua_type(L,-1) == LUA_TNIL` takes
the `lua_settop(L,-2)` arm. Any non-nil type takes the other arm, copies input
one, and attempts `lua_call(L,1,0)` without a callability test. Both normal
arms converge at `0x002e9f9d` with the entry Lua stack restored.

The callback then directly calls helper `0x002e9f00` at `0x002e9fa0`. Its
native tail conditionally performs indirect `call [EAX]` at `0x002e9faf`, then
conditionally calls target `0x0036fb17` at `0x002e9fbb` after comparing a
reloaded pointer with `EDI + 8`. The latter target may carry a local
`FID_conflict:_free` label, but that label is not semantic evidence. The
callback returns zero Lua results at `0x002e9fc4`--`0x002e9fc8`.

The artifact may say “guarded non-nil lookup/call followed by a native
cleanup-shaped tail.” It must not claim successful lookup or invocation,
callability, runtime `__gc` dispatch, finalization, destructor/free semantics,
allocation origin, ownership, or lifetime.

## Operator-dispatch acceptance grammar

### Complete Lua-call partition

The wrapper has exactly these 15 direct `FF 15` Lua-import calls:

```text
0x002ea1b2  lua_touserdata      0x002ea1c3  lua_getmetatable
0x002ea1d5  lua_rawgeti         0x002ea1de  lua_tocfunction
0x002ea1f1  lua_settop          0x002ea1ff  lua_gettop
0x002ea20d  lua_pushvalue       0x002ea215  lua_gettable
0x002ea21e  lua_type            0x002ea24f  lua_gettop
0x002ea264  lua_pushstring      0x002ea26b  lua_error
0x002ea27e  lua_insert          0x002ea2ae  lua_remove
0x002ea2bb  lua_call
```

It has exactly four additional register-dispatched Lua calls:

```text
0x002ea22b  stage EBX = [lua_settop IAT]  -> call EBX 0x002ea234
0x002ea23b  stage EBX = [lua_settop IAT]  -> call EBX 0x002ea25c
0x002ea284  stage EDI = [lua_toboolean IAT]
                                            -> call EDI 0x002ea290
                                            -> call EDI 0x002ea2a2
```

The stage-to-call proofs must reject intervening register writers, alternate
atlas entries, or declared direct-call entries. They rely on the explicit x86
Windows cdecl nonvolatile-register premise across intervening calls. Audit all
eight one-byte `call r32` encodings over the complete body, not just EBX/EDI.

The recognizer has exactly five direct calls and no register-dispatched Lua
call:

```text
0x002ea3d9  lua_touserdata
0x002ea3ea  lua_getmetatable
0x002ea3fc  lua_rawgeti
0x002ea405  lua_tocfunction
0x002ea418  lua_settop
```

Thus the operator artifact seals 20 direct calls and four staged calls. It
must reject any incomplete body-local direct or register-call partition.

### Wrapper two-input search

Let the entry stack be `S = [I1,...,IN]`, captured key be `K`, and captured
Boolean be `B`. The body contains no entry arity guard.

`EDI` starts at one at `0x002ea1a9`. For each examined index `i`, the callback:

1. requires non-null `lua_touserdata(L,i)`;
2. requires `lua_getmetatable(L,i)` to succeed;
3. reads numeric metatable slot one with `lua_rawgeti(L,-1,1)`;
4. requires `lua_tocfunction(L,-1) == 0x002ea110`;
5. restores the entry stack through `lua_settop(L,-3)`;
6. pushes upvalue one (`lua_upvalueindex(1) == -10003`) and evaluates
   `lua_gettable(L,i)`.

A nil candidate is popped with staged `lua_settop(L,-2)` and continues. The
increment/compare sequence at `0x002ea241`--`0x002ea248` examines exactly
indices one and two; it never examines input three.

On a non-nil candidate `V`, `lua_insert(L,1)` produces
`[V,I1,...,IN]`. Upvalue two (`lua_upvalueindex(2) == -10004`) is read twice.
When false, the saved entry top `N` is passed as `nargs`. When true, `nargs`
becomes one and `lua_remove(L,3)` is attempted. The normal expected two-input
shape is therefore:

```text
B = false: [V,I1,I2] -> lua_call(V, 2 args, 1 result)
B = true:  [V,I1,I2] -> remove absolute slot 3 -> [V,I1]
                        -> lua_call(V, 1 arg, 1 result)
```

For `B = false`, larger `N` changes the call arity. The true arm must not be
generalized to arbitrary `N`; its absolute-slot-three removal is only the
well-formed intended reduction under the expected stack shape. The call
requests one result and the callback returns one on normal success.

If neither input supplies a non-nil candidate, `lua_gettop` plus the computed
index `-top-1` clears the stack, then the callback pushes this exact literal:

| role | RVA | printable bytes | bytes including NUL | NUL-inclusive SHA-256 | section |
| --- | --- | ---: | ---: | --- | --- |
| `No such operator defined` | `0x0043c4a4` | 24 | 25 | `d16f10ee15af8c2e95b531a7149f4063e4c2239b47ac228e943c74e08712ad56` | `.rdata`, RVA `0x003d6000`, characteristics `0x40000040`, non-writable |

`lua_error` is called at `0x002ea26b`. Under the Lua 5.1 premise it does not
return normally. The machine fallthrough still sets result zero at
`0x002ea274` and returns at `0x002ea27a`; record that as a fallback CFG
terminal, not a normal Lua-error result count.

### Recognizer predicate

Under its observed `ECX = L`, `EDX = index` register convention, helper
`0x002ea3d0` returns the original non-null `lua_touserdata` result exactly when:

1. `lua_touserdata(L,index)` is non-null;
2. `lua_getmetatable(L,index)` succeeds;
3. numeric metatable slot one, read through `lua_rawgeti(L,-1,1)`, converts
   through `lua_tocfunction` to callback `0x002ea110`.

The tested metatable and slot are removed with `lua_settop(L,-3)` before
return. Null userdata and absent-metatable arms return zero without having
pushed values. A mismatch zeroes the saved userdata pointer before the same
stack restoration. Normalize this as a reusable native pointer recognizer, not
as factory provenance, type identity, ownership, or source-level class proof.

## Complete target-reference partitions

The implementation must exhaustively decode all 25,490 atlas ranges,
3,735,718 body bytes, and 1,153,814 instructions with operand detail enabled.
Across all four entry VAs, the exact result is 79 immediate operand-zero
references, with no absolute-memory reference and no other retained immediate
class:

| target | exact class | source instruction | owner | instruction SHA-256 |
| --- | --- | --- | --- | --- |
| `0x002e9f00` | direct relative call | `0x002e9fa0` | `0x002e9f40` | `05a2387faabb45c2821bc075bd423d975ba4c162bcc17c415bc1ede909d237df` |
| `0x002e9f40` | cleanup closure producer | `0x002ea32b` | `0x002ea2d0` | `5a8636738d6c58ab5c150bb57671f43af26c38d52799570d38d1584202bcc57b` |
| `0x002ea1a0` | wrapper closure producer | `0x002ea3a7` | `0x002ea2d0` | `33e9988ef68a664f937a5920541f4beb1f1cf901ac168c2486e17d9fa2749c24` |
| `0x002ea3d0` | 76 direct relative calls | listed below | 76 distinct owners | per-row exact join required |

The initializer owner at `0x002ea2d0` has atlas-record SHA-256
`9bebfe870176e21574adce7ab56dc323785c19e0cdb73d03afc267a3edf84c1f`.
The two closure rows must also rejoin the exact placement records in the
initializer artifact.

The exact recognizer `owner:call` rows are:

```text
054610:05463c 054690:0546bc 060ca0:060d00 067000:067010
067080:06708f 0670e0:06710c 067270:067282 067380:06738f
067610:067620 067690:0676a2 067710:067722 067a90:067af8
0688e0:0688f1 068950:068961 0689c0:0689d1 075e90:075ebb
07cbf0:07cc1b 0a97b0:0a97db 0c6ff0:0c701b 10db80:10dbac
1781a0:1781cc 198e70:198ef3 1b3500:1b352c 205e10:205e7f
226d50:226d7b 244c70:244c9c 291fb0:291fd8 292030:292058
2920b0:2920d9 2dd660:2dd671 2dd6d0:2dd6e1 2dd740:2dd751
2dd7b0:2dd7c2 2dd8d0:2dd8e1 2dd940:2dd951 2dd9b0:2dd9c1
2dda20:2dda4c 2ddac0:2ddad1 2ddb30:2ddb40 2ddbb0:2ddbc1
2ddc20:2ddc31 2ddd90:2ddda1 2dde00:2dde11 2dde70:2dde82
2ddef0:2ddf01 2ddf60:2ddf71 2de060:2de071 2de330:2de35c
2de3d0:2de3fc 2de500:2de511 2de570:2de581 2de670:2de682
2de6f0:2de702 2de770:2de782 2de7f0:2de802 2de870:2de880
2de8f0:2de902 2de970:2de982 2de9f0:2dea02 2dea70:2dea82
2deaf0:2deb02 2deb70:2deb82 2debf0:2dec02 2dec70:2dec82
2decf0:2ded02 2ded70:2ded82
2e2560:2e2571 2e25d0:2e25e0 2e2650:2e2661 2e26c0:2e26d1
2e2730:2e2741 2e27a0:2e27b1 2e2810:2e2821 2e2880:2e2891
2e28f0:2e2901 2e2960:2e2971
```

Every normalized reference row must carry the owning atlas entry and its
canonical atlas-record hash, instruction bytes/hash, operand index and class,
and target RVA. The tests must pin 76 rows, 76 owners, 77 operator-target
references, two cleanup-target references, and 79 combined references. These
counts do not exclude computed pointers, data references outside decoded
operands, un-atlased code, indirect calls, or Lua-side behavior.

## Minimum focused tests

Both artifacts must exercise:

- deterministic rebuild and canonical hash stability;
- structural validation without a PE and exact validation with the pinned PE;
- rejection of prerequisite identity drift, body/atlas/CFG drift, point-byte
  drift, direct-call partition drift, staged-register provenance drift, target
  reference count/class/owner drift, and literal byte/section drift;
- immutable writer behavior for identical and non-identical existing files;
- summary totals that are recomputed from normalized records rather than
  trusted as free fields;
- semantic-grammar mutation tests for every branch distinction stated above;
- conservative nonclaims, especially wrapper entry arity, candidate
  callability, recognizer caller meaning, and cleanup ownership/lifetime.

The operator tests must separately mutate the loop bound, getter callback
identity, both upvalue pseudo-indices, both Boolean reads, absolute removal
index three, saved `nargs`, requested result count one, error clearing formula,
and fallback terminal. The cleanup tests must separately mutate the unsigned
count branch, registry index `-10000`, byte-wise pointer increment, nil/non-nil
lookup split, helper edge, indirect native edge, conditional tail target, and
zero-result return.

## Explicit nonclaims

Neither artifact proves runtime execution or reachability, successful Lua API
calls or allocations, dynamic metatable attachment, lookup success, selected
value callability, Lua metamethod invocation, source-language operator or
property contracts, arbitrary entry arity behavior, factory provenance from
callback identity, semantic homogeneity of recognizer callers, registry-key
meaning, runtime `__gc` dispatch, native destructor/free semantics, allocation
origin, ownership, lifetime, state continuity, or completeness beyond the
finite executable, atlas, imports, literals, CFGs, and operand scans stated
here.
