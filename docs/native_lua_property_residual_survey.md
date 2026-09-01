# Native Lua `property` residual-path survey

Status: promoted exact-build static research checkpoint. The two
identity-mismatch traces are normalized by the dependent mismatch-path
artifact. The initializer's marker, `__gc` closure placement, and 13-entry
operator-wrapper construction loop are normalized by a second dependent
artifact. Cleanup-callback/helper behavior and its two-reference frontier are
normalized by a third dependent artifact. The wrapper callback, reusable
native recognizer, and complete 77-reference / 76-owner frontier are normalized
by a fourth. Their implemented exact acceptance boundary remains recorded in
`docs/native_lua_property_callback_artifact_spec.md`. These are finite binary
proofs, not recovered source or runtime execution evidence.

## Bound inputs and notation

All claims are specific to the x86 Windows `Breach.exe` from build `13725832`,
SHA-256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
They reuse:

- Program-facts atlas canonical SHA-256
  `631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803`.
- Direct Lua-call census canonical SHA-256
  `07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608`.
- Property-factory artifact canonical SHA-256
  `aef6475375ce31da7d089eb819bf4b3a42228332892aa2bb8645668fe2db3b5e`.
- Property-consumer artifact canonical SHA-256
  `2c6569177595cbdc8abdbe4ba1bdc3d09f4bb0d15dac5d280c16ba3dfcc2d3b9`.
- Property-mismatch artifact canonical SHA-256
  `49276d63020a536bdd456d3f36667428afff2b3d8b15e479eb5444c241b23263`.
- Property-initializer artifact canonical SHA-256
  `b76b3d46d30da4801a3bc4f67be78d3818f847557a0b275f6048120873b44bc4`.

Let the entry Lua VM stack be `S = [I1, ..., IN]`. The getter trace requires
`N >= 2`; the setter trace requires `N >= 3`. `F` is the one value pushed by
`lua_getfenv(L,1)`, `D` is the first raw lookup result, `M` a metatable, `W`
the metatable fallback lookup, `C` the selected candidate, and `T` a freshly
created table.

The stack traces use the Lua 5.1 API premises that positive indices are
absolute, negative indices are relative to the current top, `lua_rawget` pops
its key and pushes the raw value, a failed `lua_getmetatable` pushes nothing,
`lua_replace(i)` moves the top value to `i` and pops the top, and
`lua_settop(-2)` pops one value. Native x86 argument pushes and caller cleanup
do not alter the Lua VM stack. Normal-return traces exclude Lua errors, long
jumps, and allocation failures.

## Getter mismatch path

The getter-like consumer at `0x002ea110` is 144 bytes with body SHA-256
`af02593b529264569e721d6dd2e401afd5d5b2b5d8aea67ee623226bfe3584a2`
and sealed CFG canonical SHA-256
`bf0b0d9be19d193c9fa79b582566a9d696d73eb98d466459e0e548a5bddf1c55`.
Its exact candidate-source partition is:

1. `lua_getfenv(L,1)` at `0x002ea11b` gives `S,F`.
2. Staged `lua_pushvalue(L,2)` at `0x002ea12a`, followed by
   `lua_rawget(L,-2)` at `0x002ea12f`, gives `S,F,D` where
   `D = raw F[I2]`.
3. `lua_type(L,-1)` at `0x002ea138`, `test eax,eax` at `0x002ea141`, and
   `jne` at `0x002ea143` select `D` directly when it is non-nil.
4. When `D` is nil, `lua_getmetatable(L,-2)` at `0x002ea148` probes `F`.
   A false result branches at `0x002ea153` with `S,F,nil`. A true result
   gives `S,F,nil,M`; a second copied `I2` and `lua_rawget(L,-2)` at
   `0x002ea15d` give `S,F,nil,M,W`. This body deliberately does not remove
   the buried nil and metatable.

All three arms put `C` on top. `lua_tocfunction(L,-1)` at `0x002ea169`
is compared with callback `0x002eaa50` at `0x002ea172`. The mismatch branch
at `0x002ea177` jumps directly to the shared native epilogue. It performs no
further Lua API call, loads C result count one at `0x002ea198`, and returns at
`0x002ea19f`.

The three distinct terminal internal stacks and selected result are therefore:

```text
environment value non-nil:       S,F,D         -> result D
nil and no environment metatable: S,F,nil       -> result nil
environment metatable fallback:  S,F,nil,M,W   -> result W
```

This proves “return the top candidate as one Lua result,” not a common terminal
stack shape. `W` may itself be nil. The mismatch is callback-pointer
inequality; it is not a type, callability, or provenance classification. No
upvalue retrieval or `lua_call` occurs on this path.

## Setter mismatch path

The setter-like consumer at `0x002e9fd0` is 317 bytes with body SHA-256
`89dcd9a4a320eb36f3c9d96c3bd24dc0c27c48b7c15dfb78fbd6ad6a59191c68`
and sealed CFG canonical SHA-256
`e8e40b27127b5089c437dc21970c5a239b6e67e76aa779dbd9a680047887dda4`.

Its first lookup is the setter analogue of the getter path:

```text
start                       S
lua_getfenv(1)              S,F
pushvalue(2); rawget(-2)    S,F,D
```

When `D` is nil, `lua_getmetatable(L,-2)` at `0x002ea00f` probes `F`.
If present, the second raw lookup initially leaves `S,F,nil,M,W`.
`lua_replace(L,-3)` at `0x002ea02d` and staged `lua_settop(L,-2)` at
`0x002ea036` normalize that arm to `S,F,W`. The non-nil direct and absent
metatable arms are already `S,F,D` and `S,F,nil`, so all normal sources
converge to `S,F,C`.

After `lua_tocfunction(L,-1)` at `0x002ea03e`, comparison with
`0x002eaa50` at `0x002ea047`, and mismatch branch `0x002ea04c`, staged
`lua_settop(L,-2)` at `0x002ea0ac` removes `C` and restores `S,F`.

### Absolute-slot-four branch

The next call is exactly `lua_getmetatable(L,4)` at `0x002ea0b1`. Define
`X = stack[4]` at that point. This distinction matters:

```text
N == 3: S,F = [I1,I2,I3,F], so X is F
N >= 4: X is original input I4, while F is at absolute slot N+1
```

The body has no `lua_gettop` or argument-count guard. Describing this call as
an unconditional environment-metatable test would therefore be too strong.
It is an environment test only under the conventional exactly-three-argument
`__newindex` invocation premise.

If `X` has a metatable, the call pushes `M_X`; staged
`lua_settop(L,-2)` at `0x002ea0eb` discards it and restores `S,F`. The common
tail copies original `I2` and `I3` at `0x002ea0f3` and `0x002ea0f8`, then
`lua_rawset(L,-3)` at `0x002ea0fd` performs the raw store `F[I2] = I3`.
The terminal internal stack is `S,F`, and the callback returns zero results at
`0x002ea106`.

If `X` lacks a metatable, `lua_createtable(L,0,0)` at `0x002ea0c1` gives
`S,F,T`. The body duplicates `T` at `0x002ea0ca` and calls
`lua_setfenv(L,1)` at `0x002ea0cf`, which consumes the duplicate. It then
copies absolute slot four, calls `lua_setmetatable(L,-2)` at `0x002ea0dd`,
and consumes that copied `X`, leaving `S,F,T`. The common tail raw-stores
`T[I2] = I3` and returns zero with internal stack `S,F,T`.

Both setter paths use `lua_rawset`, so the exact stores bypass Lua table
metamethod dispatch. The return values of `lua_setfenv` and
`lua_setmetatable` are ignored; the binary attempts those mutations but does
not prove they succeeded. Under the conditional `N == 3` premise, the branch
can be summarized as “if `F` has a metatable, store in `F`; otherwise create
`T`, attempt to set `T` as `I1`'s environment and `F` as `T`'s metatable,
then store in `T`.” Without that premise, the tested and copied value is `I4`.

## Residual initializer table grammar

The initializer at `0x002ea2d0` is already sealed by the consumer artifact:
245 bytes, body SHA-256
`87e765ce2290b8320efb30cb7e110e8ae67783793b968aecd01827f6bd00d9c1`,
and CFG canonical SHA-256
`3901fcde5bfae4be68f67fa1af3cd5e2831443d3af26d16f85c90576d781a843`.
Beyond the normalized numeric getter, `__index`, and `__newindex` placements,
it has the following exact grammar.

### Marker and `__gc`

`lua_createtable(L,0,0)` at `0x002ea2da` creates `T`. The body pushes boolean
true at `0x002ea2e3` and performs staged
`lua_setfield(L,-2,"__luabind_class")` at `0x002ea2f7`. The key is the exact
15-byte non-writable literal at `0x0043c524`, with NUL-inclusive SHA-256
`7820ddb1dbf79226b867dd156f8b7cb7f8faa8c6700fa20c66e3f4c1dbd47e20`.
This proves a field placement in `T`, not a source-level type name.

The initializer then pushes zero upvalues and callback `0x002e9f40` at
`0x002ea329` and `0x002ea32b`, creates the closure at `0x002ea331`, and
places it with staged `lua_setfield` at `0x002ea33b` under `__gc`. The key is
at `0x0043bf84`, with NUL-inclusive SHA-256
`6b3cc554d45a56ed43995cc307f4481a80680a993cd06b4ecfef70986c17997e`.

Callback `0x002e9f40` is 137 bytes with body SHA-256
`42a2e05350e953d42a76c65c17f665e384fd53bc3ef4e1d578681a10c48008ba`
and seven direct Lua-import calls. It:

1. obtains `lua_touserdata(L,1)` at `0x002e9f4b`;
2. pushes `__finalize` from `0x0043c50c` and calls
   `lua_gettable(L,1)` at `0x002e9f62`;
3. tests `lua_type(L,-1)` at `0x002e9f6b`;
4. pops a nil value at `0x002e9f7b`, or for any non-nil value copies input
   one and calls `lua_call(L,1,0)` at `0x002e9f94` without a callability test;
5. converges on direct native helper call `0x002e9fa0`, then an indirect
   vtable call and conditional native free-like tail through `0x002e9fc0`;
6. returns zero Lua results at `0x002e9fc4`-`0x002e9fc8`.

The `__finalize` literal is ten bytes excluding its NUL terminator and 11 bytes
including it, with NUL-inclusive SHA-256
`2da9eac9965b6b70aa210a588888733805c3214ecd627e37afd1aa1909b100b7`.
This is a finite guarded lookup and call followed by a native cleanup-shaped
tail. It does not prove runtime `__gc` dispatch, call success, finalization,
destructor semantics, allocation origin, ownership, or resource lifetime.

The direct helper at `0x002e9f00` is 64 bytes with body SHA-256
`65d5712025be3aeb9d3bec9845edf4aec64fb7aaaf04ea706b5482d8d43305eb`.
For the unsigned count at native offset `+0x2c`, it loops byte offsets from
zero to count minus one, pushes `lightuserdata(native_pointer + offset)`,
pushes nil, and performs `lua_rawset(L,LUA_REGISTRYINDEX)`. Its only direct
operand reference in the atlas is call `0x002e9fa0`. The source meaning of
the native pointer, count, and registry keys remains unassigned.

### Thirteen two-upvalue wrapper closures

The initializer's loop begins with zero at `0x002ea36b`, increments at
`0x002ea3b8`, and repeats while the zero-based index is below 13 at
`0x002ea3bc`-`0x002ea3bf`. The 52-byte pointer array at `0x0043c53c` has
SHA-256
`95c565ed90ed86b684d214cb95b79de28ecb376e05f58852f091dec49bd6766c`.
It names this exact ordered partition:

| index | key | literal RVA | Boolean upvalue |
| ---: | --- | --- | --- |
| 0 | `__add` | `0x00420730` | false |
| 1 | `__sub` | `0x00420738` | false |
| 2 | `__mul` | `0x00420748` | false |
| 3 | `__div` | `0x0043c404` | false |
| 4 | `__pow` | `0x0043c41c` | false |
| 5 | `__lt` | `0x0043c424` | false |
| 6 | `__le` | `0x0043c40c` | false |
| 7 | `__eq` | `0x00420740` | false |
| 8 | `__call` | `0x0043c414` | false |
| 9 | `__unm` | `0x0043c440` | true |
| 10 | `__tostring` | `0x0043c448` | false |
| 11 | `__concat` | `0x0043c42c` | false |
| 12 | `__len` | `0x0043c438` | true |

Each iteration pushes the key string at `0x002ea378`, duplicates it at
`0x002ea381`, computes a Boolean that is true only for indices 9 and 12 at
`0x002ea38a`-`0x002ea398`, and pushes that Boolean at `0x002ea39f`. It then
pushes upvalue count two and callback `0x002ea1a0` at `0x002ea3a5` and
`0x002ea3a7`, creates the closure at `0x002ea3ad`, and performs
`lua_settable(L,-3)` at `0x002ea3b2`.

The exact per-iteration VM trace is:

```text
[T] -> [T,K] -> [T,K,K] -> [T,K,K,B]
    -> [T,K,C] via lua_pushcclosure(L,0x002ea1a0,2)
    -> [T] via lua_settable(L,-3)
```

Thus, every wrapper closure captures its key as upvalue one and the Boolean as
upvalue two. The closures are not zero-upvalue closures, and the two true flags
must not be generalized to the other eleven rows.

## Wrapper callback and numeric-slot recognizer

### Two-input wrapper callback

Callback `0x002ea1a0` is 302 bytes with body SHA-256
`bea28c212b1b1b163611046a80f2c3da4c4886aaa1bea785bde455f7b0e5b9a3`
and 15 direct Lua-import calls. Its normal search loop examines exactly Lua
input indices one and two, not one through three:

1. `lua_touserdata(L,i)` at `0x002ea1b2` must be non-null.
2. `lua_getmetatable(L,i)` at `0x002ea1c3` must succeed.
3. `lua_rawgeti(L,-1,1)` at `0x002ea1d5` reads numeric slot one.
4. `lua_tocfunction(L,-1)` at `0x002ea1de` must equal getter callback
   `0x002ea110` at comparison `0x002ea1e6`.
5. `lua_settop(L,-3)` at `0x002ea1f1` restores the entry stack before the
   result is used.

On a marker match, the callback pushes captured key upvalue one at
`0x002ea20d` and performs `lua_gettable(L,i)` at `0x002ea215`. A non-nil
result reaches the call arm; nil continues to the other input. If neither
input yields a value, the body clears the Lua stack, pushes
`No such operator defined` from `0x0043c4a4`, and calls `lua_error` at
`0x002ea26b`. The message is 24 bytes with NUL-inclusive SHA-256
`d16f10ee15af8c2e95b531a7149f4063e4c2239b47ac228e943c74e08712ad56`;
that length excludes the one-byte NUL terminator, so the hashed span is 25
bytes.

On success, `lua_insert(L,1)` at `0x002ea27e` moves the selected value below
the original inputs. Captured Boolean upvalue two is read twice through staged
`lua_toboolean` calls at `0x002ea290` and `0x002ea2a2`. False keeps the saved
entry argument count as `nargs`. True changes `nargs` to one and executes
`lua_remove(L,3)` at `0x002ea2ae`. `lua_call(L,nargs,1)` at `0x002ea2bb`
then returns one Lua result at `0x002ea2c4`-`0x002ea2cd`.

There is no entry arity guard. In particular, the true-flag path is only a
well-formed `[callee,argument]` call under the expected stack shape that makes
removing absolute slot three discard the extra input. The exact captured key
names support an operator-wrapper description, but the binary does not prove
Lua metamethod invocation, lookup success, returned-value callability, or a
source-language operator contract.

### Reusable native recognizer

Native helper `0x002ea3d0` is 93 bytes with body SHA-256
`fb64dfb22aa5813027232506af9b60f97a85e1d5b79b7d63182dc4ce957f02c0`
and five direct Lua-import calls. Under its observed `ECX = L`, `EDX = index`
register convention, it:

1. obtains `lua_touserdata(L,index)` at `0x002ea3d9`;
2. requires `lua_getmetatable(L,index)` at `0x002ea3ea` to succeed;
3. reads numeric slot one with `lua_rawgeti(L,-1,1)` at `0x002ea3fc`;
4. compares `lua_tocfunction(L,-1)` with getter `0x002ea110` at
   `0x002ea40d`;
5. restores the stack with `lua_settop(L,-3)` at `0x002ea418`;
6. returns the original non-null userdata pointer only on that identity match,
   and returns zero otherwise.

This is a reusable native recognizer-like helper, not another initializer
closure. The complete atlas has exactly 76 direct `call rel32` operands to it,
from 76 distinct function entries, and no other immediate or absolute-memory
reference to its entry VA.

## Finite target-reference partitions

An exhaustive operand-detail decode of all 25,490 atlas ranges, 3,735,718
bytes, and 1,153,814 instructions gives this exact partition:

- target `0x002e9f40`: one immediate closure-target push at `0x002ea32b`;
- target `0x002ea1a0`: one immediate closure-target push at `0x002ea3a7`;
- target `0x002ea3d0`: 76 direct relative calls, with no other operand use;
- target `0x002e9f00`: one direct relative call at `0x002e9fa0`.

The first three targets therefore have 78 references total: two closure
producers and 76 direct calls. Adding the cleanup helper gives 79. There are no
absolute-memory operands or other direct-address classes in this declared
partition. This does not exclude computed pointers, data references outside
decoded operands, un-atlased code, indirect calls, or Lua-side behavior.

## Normalization boundary and nonclaims

`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_property_mismatch_chain.json`
has analysis kind `pe_native_lua_property_mismatch_chain`. Its pretty-printed
SHA-256 is
`dcae907285c435a8ac178a65bb4c1edb341f0b6cfdd35597b5d2cd57306bdb63`;
its canonical JSON SHA-256 is
`49276d63020a536bdd456d3f36667428afff2b3d8b15e479eb5444c241b23263`.
The artifact recursively verifies the exact property-consumer chain, binds the
two 461-byte source bodies and their full 190-node / 195-edge CFG identity,
and rejoins 78 declared path points to their sealed CFG nodes and proven direct
or register-staged Lua API identities. Its structural validator performs the
same derivation without reopening the PE; its exact validator rebuilds through
the complete prerequisite chain and byte-compares canonical evidence.

This artifact promotes only the getter and setter mismatch traces. The
dependent artifacts below separately seal initializer placement, cleanup, the
wrapper callback, the recognizer, and its 76-call frontier. The split preserves
the wrapper's exact two-input loop just as the mismatch artifact preserves the
setter's conditional absolute-slot-four relation.

`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_property_initializer_chain.json`
has analysis kind `pe_native_lua_property_initializer_chain`. Its
pretty-printed SHA-256 is
`21aa8589ea24fc5b0f468781bb27c299d7df3f75927fc2202dbe5d08dec18872`;
its canonical JSON SHA-256 is
`b76b3d46d30da4801a3bc4f67be78d3818f847557a0b275f6048120873b44bc4`.
It recursively verifies the consumer artifact, rejoins 33 exact initializer
points to the sealed 89-node / 91-edge CFG and direct or staged Lua API calls,
and exact-rereads 15 NUL-terminated literals plus the 52-byte, 13-pointer
operator array. The resulting grammar records
`T["__luabind_class"] = true`, the zero-upvalue `__gc` closure placement,
and each two-upvalue wrapper closure with upvalue order `[K,B]`. It does not
normalize behavior inside either callback; the two dependent callback artifacts
below do so under their own narrower grammars.

`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_property_cleanup_chain.json`
has analysis kind `pe_native_lua_property_cleanup_chain`. Its pretty-printed
SHA-256 is
`71e22903dc54d2e1088221e61140b12374def39883813c6474c0335f09d4ca88`;
its canonical JSON SHA-256 is
`e2aaf57a9560f806814977ee30a48ce4d3afae35d00e78e3bcb39ebb9bfb7483`.
It recursively exact-verifies the initializer chain, seals the 201-byte
cleanup callback/helper pair and their 83-node / 86-edge CFG identity, joins
all ten direct Lua calls, exact-rereads the 11-byte NUL-inclusive `__finalize`
literal, and exhaustively reproduces the helper call plus initializer closure
producer as the only two direct target references. Its structural validator
replays the normalized evidence without reopening the PE; its exact validator
redecodes both bodies and all 25,490 atlas ranges. This promotes only the
cleanup pair; the companion artifact below covers the wrapper and recognizer.

`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_property_operator_dispatch_chain.json`
has analysis kind `pe_native_lua_property_operator_dispatch_chain`. Its
pretty-printed SHA-256 is
`6b3a33905b8a36463e32fbda680ad86fe21d4ae04dea6cab59bf7b2c4ff0f239`;
its canonical JSON SHA-256 is
`7db59f62fc9d70e3b2338bc0349afae91ee8c7b34099cd3b034c6c240b035fdc`.
It recursively exact-verifies the initializer chain, seals the 395-byte
wrapper/recognizer pair and their 155-node / 159-edge CFG identity, joins all
20 direct Lua calls and four register-staged calls, exact-rereads the 25-byte
NUL-inclusive `No such operator defined` literal, and exhaustively reproduces
the initializer wrapper producer plus 76 direct recognizer calls from 76
distinct owners as the complete 77-reference partition. The staged-call proof
uses exact last reaching definitions, including both `0x002ea22b` and
`0x002ea23b` at error-path call `0x002ea25c`. Its structural validator replays
the normalized evidence without reopening the PE; its exact validator redecodes
both bodies and every atlas range. Together the two callback artifacts seal
596 body bytes, 238 nodes / 245 edges, 30 direct Lua calls, four staged calls,
and the complete 79-reference four-target partition described above.

This survey does not prove runtime execution, successful API calls or
allocations, callback callability, factory provenance from callback identity,
entry arity, dynamic table or metatable attachment, later lookup or invocation,
durable read-only enforcement, mutation success, native destructor or free
semantics, allocation origin, registry-key meaning, ownership, lifetime,
source-level class/property/operator equivalence, state continuity, or
completeness beyond the finite executable, atlas, imports, literals, and
operand grammars stated above.
