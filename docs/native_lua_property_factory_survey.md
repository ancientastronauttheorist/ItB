# Native Lua `property` factory survey

Status: read-only static research checkpoint. This note follows one finite
native callback chain in the Windows executable. It does not reconstruct a C++
or Lua source implementation and does not establish runtime reachability.

## Bound inputs

All claims are specific to the x86 Windows `Breach.exe` from build `13725832`,
SHA-256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
They join these exact artifacts:

- Program-facts atlas, canonical SHA-256
  `631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803`.
- Direct Lua import-call census, canonical SHA-256
  `07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608`.
- Closure table-key provenance census, canonical SHA-256
  `8b8cab571c3c8945dae440933107022b35eed28b4c806a35188202bd52073db6`.
- Closure terminal-disposition census, canonical SHA-256
  `74b762e486611a6dc71325276d9e8e92b7894de30f99bacf9e301e894c85bb85`.

Addresses are image-relative RVAs. Lua API stack effects, type value zero for
nil, and the non-returning behavior of `lua_error` are Lua 5.1 ABI premises.

## Global publication

The table-key census proves the following exact publication in the 811-byte
constructor at `0x002e6900` (body SHA-256
`0723567170e15f7f36f25c97f15257ce9aabaaff57ace1bdf7778810a9158886`):

| role | RVA |
| --- | --- |
| push literal pointer `property` | `0x002e6bb2` |
| staged `lua_pushstring` | `0x002e6bb8` |
| push zero upvalues / callback `0x002e67b0` | `0x002e6bba` / `0x002e6bbc` |
| `lua_pushcclosure` | `0x002e6bc2` |
| `lua_settable(L, LUA_GLOBALSINDEX)` | `0x002e6bd1` |

The `property` literal is at `0x0043bf8c`, is eight bytes excluding its NUL,
has NUL-inclusive SHA-256
`e0d753a813d3d803fae7d2aa3f4f35384d2e18d4671c88af256ea5834b595010`,
and lies in non-writable `.rdata` (`0x40000040`). The evidence deliberately
does not claim a stable export: `lua_settable` is metamethod-capable, later
mutation is unexcluded, and the constructor need not run.

## Factory argument and closure grammar

The published callback at `0x002e67b0` is one 92-byte atlas body with SHA-256
`c93226f0c1ca1e6afb2be4498dddb966b3bc052a7fc71bdad123772adee83303`.
Its complete normal Lua 5.1 grammar is:

1. `lua_gettop` at `0x002e67b9` obtains the argument count.
2. The tests and branches at `0x002e67c4`-`0x002e67cb` accept exactly one or
   two arguments. Zero or more than two pushes the literal at `0x0043be24`
   with `lua_pushstring` at `0x002e67d3` and calls `lua_error` at
   `0x002e67da`.
3. Exactly one argument takes the branch at `0x002e67e3`-`0x002e67e6` and
   appends nil with `lua_pushnil` at `0x002e67e9`. Exactly two arguments do
   not alter the VM stack.
4. The function pushes upvalue count two and callback `0x002eaa50` at
   `0x002e67f2`/`0x002e67f4`, calls `lua_pushcclosure` at `0x002e67fa`, and
   returns one Lua result through `mov eax,1` at `0x002e6803` and the simple
   epilogue ending at `0x002e680b`.

Let `A1` and `A2` be the accepted arguments and `P` the returned closure. The
two successful VM traces are:

```text
one argument:  [A1]    -> [A1, nil] -> [P]
two arguments: [A1,A2]              -> [P]
                                   lua_pushcclosure(L, 0x002eaa50, 2)
```

Thus, for a factory-produced closure, upvalue 1 is exactly `A1`, and upvalue 2
is exactly `A2` or the inserted nil. The factory performs no type or
callability check.

The wrong-count literal is
`make_property() called with wrong number of arguments.` at `0x0043be24`
(54 bytes excluding NUL; NUL-inclusive SHA-256
`a5cfaa776573b35f0c3701aaad43a4331e8603e83b07cb38aa0e6e3a0a8b9956`).
It is in the same non-writable `.rdata` section.

## Returned tag callback

Callback `0x002eaa50` is one 33-byte atlas body with SHA-256
`0b8d87b0ad0d6a1535a67f930c0b4fe9960a099bd5ad08b13c3d30cbf41b223f`.
It does not read its arguments or upvalues. It pushes the literal
`luabind: property_tag function can't be called` from `0x0043c5d4` with
`lua_pushstring` at `0x002eaa5b`, then calls `lua_error` at `0x002eaa64`.
The literal is 46 bytes excluding NUL, has NUL-inclusive SHA-256
`571afe6269d164266ab1c841d2e07b422b7224f100e9c5a3953b4cdad5e68bc5`,
and is non-writable `.rdata`. If `lua_error` contrary to its ABI contract
returned, the binary fallback at `0x002eaa6d`-`0x002eaa70` would return zero.

The strongest local claim is therefore that this callback is a non-callable
tag under normal Lua 5.1 semantics. Its captured values acquire getter/setter
roles from separate consumers, not from any operation in the tag callback.

## Exact tag consumers

A complete decode of all function ranges in the atlas found four direct
immediate operands equal to callback VA `0x006eaa50`:

| RVA | use |
| --- | --- |
| `0x0005799c` | alternate two-upvalue closure producer |
| `0x002e67f4` | this factory's callback push |
| `0x002ea047` | `lua_tocfunction` result comparison in `0x002e9fd0` |
| `0x002ea172` | `lua_tocfunction` result comparison in `0x002ea110` |

This is a finite direct-immediate operand partition, not a proof against data
references, computed comparisons, indirect code, or Lua-side behavior.

### Getter-like consumer

Function `0x002ea110` is a 144-byte body with SHA-256
`af02593b529264569e721d6dd2e401afd5d5b2b5d8aea67ee623226bfe3584a2`.
It first resolves a candidate value from the environment of Lua stack index 1,
with a metatable fallback at `0x002ea145`-`0x002ea163`. It calls
`lua_tocfunction(L,-1)` at `0x002ea169` and compares the result with
`0x002eaa50` at `0x002ea172`.

On an identity match, it calls `lua_getupvalue(L,-1,1)` at `0x002ea17e`,
copies original Lua stack index 1 at `0x002ea187`, and executes
`lua_call(L,1,1)` at `0x002ea18e`. The callback returns one result at
`0x002ea197`-`0x002ea19f`. For a factory-produced tag, this treats `A1` as a
callee receiving the consumer's first argument and producing one result. The
binary does not first prove that `A1` is callable.

### Setter-like consumer

Function `0x002e9fd0` is a 317-byte body with SHA-256
`89dcd9a4a320eb36f3c9d96c3bd24dc0c27c48b7c15dfb78fbd6ad6a59191c68`.
It resolves a candidate through the environment of stack index 1 and a
metatable fallback at `0x002ea00c`-`0x002ea038`, calls
`lua_tocfunction(L,-1)` at `0x002ea03e`, and compares the result with
`0x002eaa50` at `0x002ea047`.

On an identity match, `lua_getupvalue(L,-1,2)` at `0x002ea053` pushes upvalue
2 and `lua_type(L,-1)` at `0x002ea05c` tests it. A nil value takes the exact
error arm: `lua_tolstring(L,2,NULL)` at `0x002ea06d` obtains the name used by
`lua_pushfstring` at `0x002ea07a`, followed by `lua_error` at `0x002ea081`.
The format is `property '%s' is read only` at `0x0043c488` (26 bytes excluding
NUL; NUL-inclusive SHA-256
`b83cdf75ce91828d07eb594c987ee462333675b0b761914ac215a5712f93aeea`),
again in non-writable `.rdata`.

For a non-nil upvalue 2, the consumer copies original stack indices 1 and 3
at `0x002ea08d` and `0x002ea092`, then performs `lua_call(L,2,0)` at
`0x002ea099` and returns zero at `0x002ea0a2`-`0x002ea0a8`. For a
factory-produced tag, this treats `A2` as a callee receiving the consumer's
first and third arguments and producing no result. It checks non-nil, not
callability.

### Metamethod placement

The 245-byte initializer at `0x002ea2d0` (body SHA-256
`87e765ce2290b8320efb30cb7e110e8ae67783793b968aecd01827f6bd00d9c1`)
constructs zero-upvalue closures for `0x002ea110` at `0x002ea345` and
`0x002e9fd0` at `0x002ea35c`. It places them with `lua_setfield` at
`0x002ea352` and `0x002ea366` under exact non-writable literals `__index` and
`__newindex`, respectively. Their NUL-inclusive literal hashes are
`89dfaf29ae22fb9d8fe3a5d35e57e4333d41a029db1133d12bf82eed91890c79`
at `0x0043c534` and
`e84e40a532eac289fd4cb0b893ed0c407fee00ee1f5d2036f638f9dc6af9273e`
at `0x0043c518`.

This placement supports the descriptive labels getter-like and setter-like.
It does not prove which dynamic object receives that metatable or that either
metamethod is invoked.

## Alternate producer and provenance boundary

The terminal-disposition census proves a second exact producer of callback
`0x002eaa50`: constructor `0x00057970` performs two registry
`lua_rawgeti` calls at `0x00057982` and `0x00057994`, uses their two values as
upvalues at `lua_pushcclosure` call `0x000579a2`, duplicates the resulting tag
closure, and stores a `luaL_ref` integer in a two-field native holder. This is
an exact join to the same callback identity, but it does not prove that either
registry-loaded value came from a call to global `property`.

Consequently, `lua_tocfunction(...) == 0x002eaa50` alone does not establish
factory provenance, two available upvalues, or their dynamic types. The
getter/setter data-flow claims above are unconditional about how the two
consumer branches use successfully retrieved upvalues, and conditional on a
factory-produced closure when identifying those values as `A1` and `A2`.

## Candidate fail-closed artifact

A narrow next artifact could be named
`pe_native_lua_property_factory_semantics`. It should compose the four bound
prerequisites and retain:

- the exact global-key publication and zero-upvalue factory callback;
- the factory argument-count CFG, nil-padding arm, two-upvalue stack trace,
  one-result epilogue, and wrong-count literal;
- the returned tag callback and its non-callable error path;
- the complete direct-immediate `0x006eaa50` operand partition;
- the two identity comparisons, exact upvalue indices, consumer argument
  copies, `lua_call` arities/result counts, and read-only error arm;
- the `__index`/`__newindex` closure placement facts; and
- the alternate registry-holder producer as a separately labeled provenance
  class rather than evidence of factory origin.

Minimum adversarial tests should independently mutate the global key or table
index, argument-count branches, nil padding, tag callback, upvalue count/order,
result count, any literal byte/hash/section characteristic, `lua_error` call,
consumer identity comparison, `lua_getupvalue` index, copied stack argument,
`lua_call` arity/result count, read-only nil test, metamethod key, alternate
producer classification, one direct-immediate reference, CFG predecessor or
entry audit, and every prerequisite canonical digest.

A PE-free structural validator may replay stored hashes, partitions, paths,
dominance, and declarative VM traces. Instruction decoding, branch semantics,
register-write classification, literal bytes, import identities, and the four
direct-immediate operands remain exact-executable rebuild obligations.

## Explicit nonclaims

This survey does not prove runtime execution, call success, argument or
upvalue types, callability, stable global export, tag provenance from callback
identity alone, descriptor storage, dynamic metatable attachment, later
lookup, state continuity across separate invocations, reference validity,
lifetime, ownership, source-level class/property semantics, absence of later
mutation, absence of computed or indirect consumers, or completeness beyond
the declared atlas and finite grammars above.
