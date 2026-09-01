# Native Lua `property` factory survey

Status: normalized executable-rebuilt factory and consumer evidence plus wider
read-only static research. The two committed artifacts seal publication,
producer provenance, the factory and returned callback, both identity
consumers, the read-only arm, exact closure placements, and their declared
whole-atlas target-reference partitions. They remain binary evidence rather
than recovered source or runtime semantics.

## Bound inputs

All claims are specific to the x86 Windows `Breach.exe` from build `13725832`,
SHA-256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
They join these exact artifacts:

- Program-facts atlas, canonical SHA-256
  `631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803`.
- Direct Lua import-call census, canonical SHA-256
  `07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608`.
- Immediate C-closure callback census, canonical SHA-256
  `cb594d7662778b98549bde5f460f1c9d8d0b30f3625d44953c392b8caa50b003`.
- Setfield-publication census, canonical SHA-256
  `b9a77c1e5e37f251f44b4c1fac304ddbea5251c1cad164e0538c4970417608a6`.
- Direct table-setter publication census, canonical SHA-256
  `a6333ffefd9c9d0ed42bea28b9f5a6e82afff58fc7adb26293c34b5589cb5fa9`.
- Indirect-settable publication census, canonical SHA-256
  `50790f8372d90ab11e44a483a39bd575e5af10ceb037c1aa557e4ebf801ac682`.
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

The strongest local claim is therefore that this callback reaches
`lua_error` unconditionally under the reviewed body and does not return under
the Lua 5.1 ABI premise. “Tag” is only a descriptive label; the closure itself
is callable by Lua, and its captured values acquire consumer roles elsewhere.

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
first pushes the exact binary64 constant `1.0` from `0x0043cbe0`, constructs a
zero-upvalue getter closure at `0x002ea31e`, and places it with
`lua_rawset(L,-3)` at `0x002ea323`. This is a numeric-key placement, not the
`__index` placement. The constant bytes are `000000000000f03f`, with SHA-256
`6c3c396ed6b5c36dcae172271f462051b1266b851e92df3deea8ac65478fd712`.

The initializer then constructs zero-upvalue closures for `0x002ea110` at
`0x002ea345` and
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

## Normalized executable-rebuilt core artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_property_factory_chain.json`
has analysis kind `pe_native_lua_property_factory_chain`. Its pretty-printed
file SHA-256 is
`5859871e2a61522a7f80a3b92f12ed705ad906b770c1fa2247877f16a066fa4b`;
its canonical JSON SHA-256 is
`aef6475375ce31da7d089eb819bf4b3a42228332892aa2bb8645668fe2db3b5e`.

The artifact rebuilds the unique global publication, the factory's proven
single-result two-upvalue closure, and the terminal census's separate
registry-holder producer of the same returned callback. That alternate row is
explicitly marked `factory_origin_claimed: false`, so callback identity cannot
silently acquire factory provenance.

Only callbacks `0x002e67b0` and `0x002eaa50` are normalized as bodies: 125
bytes, 45 CFG nodes, and 46 CFG edges. Their complete seven direct Lua-import
calls are joined to the census, and their complete eight-encoding x86
`call r32` partition is empty. The `property` and wrong-count literals are
published; the colon-bearing returned-callback message is retained only by
RVA, section, length, and NUL-inclusive hash.

The exhaustive scan of all 25,490 atlas ranges, 3,735,718 bytes, and 1,153,814
instructions finds exactly five operands equal to either callback VA: three
closure producers at `0x0005799c`, `0x002e67f4`, and `0x002e6bbc`, plus two
callback-identity comparisons at `0x002ea047` and `0x002ea172`. There are no
direct calls, absolute-memory references, or other immediate uses. The
consumer bodies, their match/mismatch branch semantics, the read-only arm, and
metamethod placement are deliberately left outside this core artifact for a
separate normalized consumer tranche.

The adversarial suite changes prerequisite and producer identities, factory
origin classification, literals, reviewed points, direct and dynamic-call
partitions, all eight x86 register-call encodings, sealed CFG identity, target
roles/scope, aggregates, method/summary/schema fields, and immutable-output
protections. PE-free validation replays the finite joins and partitions;
instruction/literal bytes and exhaustive decoding remain exact rebuild duties.

## Normalized executable-rebuilt consumer artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_property_consumer_chain.json`
has analysis kind `pe_native_lua_property_consumer_chain`. Its pretty-printed
file SHA-256 is
`1cc4b84cebb5b5fab17b059f8050bca477c6d27742efb267b7a29851d87d88a5`;
its canonical JSON SHA-256 is
`2c6569177595cbdc8abdbe4ba1bdc3d09f4bb0d15dac5d280c16ba3dfcc2d3b9`.

The artifact recursively exact-verifies the factory artifact, then seals the
setter-like consumer, getter-like consumer, and initializer: 706 bytes, 279
CFG nodes, and 286 CFG edges. It joins all 34 direct Lua-import calls and five
dominating EBX, ESI, or EDI import stages covering all 23 register calls. A
separate complete check of all eight x86 `call r32` encodings prevents another
register form from escaping that partition.

The normalized identity-match arms retrieve upvalues two and one respectively.
The setter's nil arm is the exact read-only `lua_error` path; its non-nil arm
copies original arguments one and three into `lua_call(L,2,0)`. The getter
copies original argument one into `lua_call(L,1,1)`. Successful upvalue
retrieval and callability are not inferred, and interpreting those upvalues as
factory arguments `A1` and `A2` remains conditional on factory provenance.
Both identity-mismatch arms remain explicitly opaque inside otherwise sealed
bodies.

The initializer records three distinct zero-upvalue placements: a getter under
numeric raw key `1.0`, a separately created getter under `__index`, and the
setter under `__newindex`. Only the latter two are labeled metamethod
placements. The three-target exhaustive atlas scan covers the same 25,490
ranges, 3,735,718 bytes, and 1,153,814 instructions and finds exactly six
references: three closure producers, two external getter-identity comparisons,
and the sole direct call to the initializer. Absolute-memory and other direct
uses are empty.

The consumer adversarial suite changes prerequisite and comparison identities,
literals, the numeric constant, reviewed points, direct and staged-call
partitions, all eight register-call encodings, semantic fields, placement
classification, exhaustive-scan rows and scope, summaries, schema fields, and
immutable-output behavior. PE-free validation replays the finite joins,
dominance proofs, CFG seals, and partitions; byte reads and exhaustive decoding
remain exact rebuild duties.

## Normalized executable-rebuilt mismatch-path artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_property_mismatch_chain.json`
has analysis kind `pe_native_lua_property_mismatch_chain`, pretty-printed file
SHA-256
`dcae907285c435a8ac178a65bb4c1edb341f0b6cfdd35597b5d2cd57306bdb63`,
and canonical JSON SHA-256
`49276d63020a536bdd456d3f36667428afff2b3d8b15e479eb5444c241b23263`.

The artifact recursively verifies the full consumer chain and promotes only
its two opaque identity-mismatch arms. It binds both source bodies and their
190-node / 195-edge CFG identity, then rejoins 78 declared path points to
sealed instructions and direct or staged Lua API identities. The getter keeps
all three distinct terminal internal stacks and selects only the top value as
its one result. The setter normalizes its candidate stack, then preserves the
critical split where absolute slot four is the appended environment only when
`N == 3`; for `N >= 4`, it is original input `I4`. All claims are limited to
normal-return stack effects and result counts.

The focused suite mutates prerequisite receipts, body and CFG joins, path
points and successors, Lua dispatch classifications, getter buried stacks,
setter normalization and slot-four relations, storage destinations, result
counts, nonclaims, summaries, schemas, and immutable-output behavior. Exact
verification rebuilds through the complete prerequisite chain; PE-free
verification repeats the derivation from the structurally verified consumer.

## Normalized executable-rebuilt initializer artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_property_initializer_chain.json`
has analysis kind `pe_native_lua_property_initializer_chain`, pretty-printed
file SHA-256
`21aa8589ea24fc5b0f468781bb27c299d7df3f75927fc2202dbe5d08dec18872`,
and canonical JSON SHA-256
`b76b3d46d30da4801a3bc4f67be78d3818f847557a0b275f6048120873b44bc4`.

The artifact recursively verifies the consumer chain, binds its 245-byte
initializer body and 89-node / 91-edge CFG identity, and rejoins 33 relevant
points to direct or register-staged Lua API calls. Exact validation rereads 15
NUL-terminated literals and the 52-byte ordered pointer array. It normalizes
the `__luabind_class` true marker, zero-upvalue `__gc` closure placement, and
all 13 two-upvalue wrapper placements. Upvalue one is the exact key and upvalue
two is a Boolean true only for `__unm` and `__len`.

This is construction and placement evidence only. The dependent cleanup-chain
and operator-dispatch artifacts now normalize behavior inside both constructed
callbacks, the cleanup callback's sole direct helper, and the wrapper's shared
numeric-slot recognizer. That does not make the behavior part of this
initializer artifact. None of these facts prove runtime dispatch or assign
source-level class, property, operator, or metamethod semantics.

The adjacent
`docs/native_lua_property_residual_survey.md` supplies the promoted mismatch
and initializer derivations. It also identifies the wrapper callback, its
numeric-slot-one getter test, a reusable 76-caller native recognizer using the
same test, and the `__gc` callback's sole direct cleanup helper. The cleanup
callback/helper pair, wrapper/recognizer pair, and their combined 79-reference
frontier are now encoded and tested. The 76 recognizer callers remain exact
operand-reachability evidence only; their heterogeneous semantics are not
classified.

## Explicit nonclaims

This survey and its artifacts do not prove runtime execution, call success,
argument or upvalue types, callability, stable global export, tag provenance
from callback identity alone, descriptor storage, dynamic metatable attachment,
later lookup or invocation, state continuity across separate invocations,
reference validity, lifetime, ownership, source-level class/property
semantics, absence of later mutation, absence of computed or indirect
consumers, or completeness beyond the declared atlas and finite grammars above.
