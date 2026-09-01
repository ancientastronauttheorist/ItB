# Native Lua `class` factory survey

Status: normalized executable-rebuilt evidence plus wider read-only static
research. The narrow committed artifact follows one build-bound native closure
chain published under the exact Lua global key `class`; it does not reconstruct
source or prove runtime behavior. Helper-internal observations later in this
document remain survey context unless explicitly listed in the normalized
artifact boundary below.

## Bound evidence

The scope is the x86 Windows `Breach.exe`, build `13725832`, SHA-256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
All RVAs are image-relative.

The chain composes these exact artifacts:

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
- Table-key provenance census, canonical SHA-256
  `8b8cab571c3c8945dae440933107022b35eed28b4c806a35188202bd52073db6`.
- Terminal-disposition census, canonical SHA-256
  `74b762e486611a6dc71325276d9e8e92b7894de30f99bacf9e301e894c85bb85`.

Lua 5.1 API interpretations use `LUA_GLOBALSINDEX == -10002`,
`LUA_REGISTRYINDEX == -10000`, and `lua_upvalueindex(1) == -10003` as ABI
premises. They do not show that a particular Lua state, table, or closure
exists at runtime.

## Publication-to-result chain

The table-key provenance census proves that constructor `0x002e6900` creates a
zero-upvalue native closure targeting `0x002ec220` at `0x002e6ba1`, with exact
key literal `class` at RVA `0x0043bf98`, and supplies it to
`lua_settable(L, LUA_GLOBALSINDEX)`. It is a static global-environment
assignment grammar, not proof of a durable export or lookup success.

The published callback has a 296-byte atlas body, SHA-256
`8a9c01de90919d67efa728e4ed9e41e9f9d68fa7f0faf0e8abbdd809cce91f9e`.
On its normal result path it creates a one-upvalue closure targeting
`0x002ec110` at `0x002ec328`; the terminal-disposition census proves that it
then returns exactly one Lua result. The returned callback has a 269-byte
atlas body, SHA-256
`a138a00ca47281aa3b4fb0db11a3aa5e875616a57b3684f7598e4b0517b900e3`.

```text
constructor 0x002e6900
  class key / global-environment setter
    -> factory callback 0x002ec220
      returns one closure carrying one userdata upvalue
        -> returned callback 0x002ec110
          returns zero results on its normal path
```

The arrows above are exact construction and return relations, not runtime
reachability, semantic class identity, or source-level method syntax.

## Factory callback grammar (`0x002ec220`)

The callback accepts a narrow normal path:

| check or action | RVAs |
| --- | --- |
| require exactly one Lua argument | `0x002ec24c` through `0x002ec25e` |
| require Lua type 4 (string) at argument 1 | `0x002ec263` through `0x002ec26f` |
| reject a string accepted by `lua_isnumber` | `0x002ec274` through `0x002ec27f` |
| error literal: `invalid construct, expected class name` | `0x002ec281` through `0x002ec28a` |
| obtain C string for argument 1 with a NULL length-output pointer | `0x002ec293` through `0x002ec298` |
| compute its NUL-terminated length and compare against `lua_objlen(1)` | `0x002ec2a3` through `0x002ec2bd` |
| error literal: `luabind does not support class names with extra nulls` | `0x002ec2bf` through `0x002ec2c8` |
| allocate 72-byte Lua userdata | `0x002ec2e1` through `0x002ec2e4` |
| native initializer of that userdata | direct call `0x002ec302 -> 0x002eacf0` |
| push the validated name, duplicate the userdata, and set global environment entry | `0x002ec307` through `0x002ec31a` |
| create returned closure with one upvalue | `0x002ec320` through `0x002ec328` |
| declare one Lua result | `0x002ec331` |

Under the Lua 5.1 stack model, immediately before the global setter the
retained stack fragment is `A,U,N,U`, where `A` is the original argument,
`U` the new userdata, and `N` the validated name. The global `lua_settable`
consumes `N,U`, leaving `A,U`; `lua_pushcclosure(..., 1)` consumes the userdata
as its one upvalue and pushes a closure. The terminal result count then retains
that closure as the single return value.

This is the strongest local static claim: on the ordinary non-error path, the
published callback validates one nonnumeric Lua string without embedded NUL,
creates a 72-byte userdata initialized by `0x002eacf0`, writes that userdata
under the string key through the Lua global-environment table setter, and
returns a closure carrying that userdata as its only upvalue. Because the
setter is `lua_settable`, not `lua_rawset`, it does not establish a raw store
or absence of metamethod effects.

## Returned callback grammar (`0x002ec110`)

The returned callback starts by retrieving its sole upvalue at
`lua_upvalueindex(1)` with `lua_touserdata` at `0x002ec132`. It then calls
`0x002eb560` twice:

| checked item | setup / helper call |
| --- | --- |
| upvalue | `edx = -10003`, `ecx = L`, call at `0x002ec15b` |
| Lua argument 1 | `edx = 1`, `ecx = L`, call at `0x002ec17f` |

`0x002eb560` uses `lua_getmetatable`, `lua_gettable`, and `lua_toboolean` to
test a metatable field keyed by exact literal `__luabind_classrep` (RVA
`0x0043c738`). The callback's normal continuation requires that helper to
return nonzero for both values. A failed upvalue check takes an assertion path
through helper RVA `0x00379cc2` at `0x002ec170`. A failed argument-1 check instead
pushes exact literal `expected class to derive from or a newline` (RVA
`0x0043c99c`) and calls `lua_error` at `0x002ec195`. It next converts argument
1 with `lua_touserdata` at `0x002ec1a1`.

The callback passes the upvalue in ECX and a two-word local whose second word
is the argument userdata to `0x002eb140` at `0x002ec1b8`. Within that helper,
the input's `+4` field is required nonzero; it iterates a structure reached at
`[input+4]+0x34`, invokes direct helpers `0x002e81f0` and `0x0006df30`, and
conditionally grows/stores an 8-byte entry in fields reached from the ECX
object. This is a field-level mutation proof only: it does not justify naming
the data structure, relationship, or ownership policy.

The returned callback then makes two ordered pairs of registry raw lookups:

| pair | first reference source | second reference source | subsequent helper |
| --- | --- | --- | --- |
| 1 | upvalue `+0x20`, rawgeti `0x002ec1cc` | argument `+0x20`, rawgeti `0x002ec1d7` | `0x002ec1db -> 0x002ec050` |
| 2 | upvalue `+0x28`, rawgeti `0x002ec1ec` | argument `+0x28`, rawgeti `0x002ec1f7` | `0x002ec1fe -> 0x002ec050` |

Each `lua_rawgeti` uses `LUA_REGISTRYINDEX`; `0x002ec050` is a 180-byte Lua
stack procedure that iterates with `lua_next`, compares field names including
`__init` and `__finalize`, and performs table operations. This proves only the
direct static calls and raw-lookup inputs. It does not prove returned registry
values are tables, that the helper succeeds, or a complete Lua VM stack effect
through those helpers.

Finally `0x002ec203` through `0x002ec20a` write the argument userdata's first
word into the upvalue userdata's first word. The normal epilogue returns zero
Lua results (`xor eax,eax` at `0x002ec20c`), while the factory closure itself
was proven to return one result when created.

## Bounded initializer facts

The factory calls `0x002eacf0` on the 72-byte userdata. Its 612-byte atlas
body initializes multiple fixed offsets and creates several registry references
through `luaL_ref`; it also conditionally unrefs prior values and reads exact
registry keys including `__luabind_classes`, `__luabind_cast_graph`, and
`__luabind_class_id_map`. This is useful provenance for the fixed offsets used
by the returned callback, but this survey deliberately does not assign those
fields semantic names or prove their later validity. The dependent exact
artifact below now normalizes this bounded body and its complete decoded
reference frontier.

## Normalized executable-rebuilt artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_chain.json`
has analysis kind `pe_native_lua_class_factory_chain`. Its pretty-printed file
SHA-256 is
`2fe1f0032564594d3b9be01e976e1c24c4ccfa60036e14432e44fc1503c6b6ae`;
its canonical JSON SHA-256 is
`824883dddbf0573c26c556d19501027c01b3031d1723ac8a493374bbf63204fc`.

The artifact rebuilds the unique `class` global-environment publication and
the returned single-result closure, then seals only callbacks `0x002ec220` and
`0x002ec110`: 565 body bytes, 199 CFG nodes, and 206 CFG edges. It proves the
complete register-call partition in those bodies: EDI-loaded
`lua_touserdata` at two calls, ESI-loaded `lua_rawgeti` at four calls, and
EBX-loaded `lua_pushstring` at three calls, each under one exact dominating IAT
stage with no intervening same-register writer or alternate modeled entry.

Six selected direct native edges are retained as exact call facts to four
unique targets. Four safe literals are re-read from the executable: `class`,
the two factory validation messages, and the returned callback error message.
The helper-internal `__luabind_classrep` literal and the initializer/helper body
interpretations from the wider survey are intentionally not normalized in this
base artifact; the edge records assign them no behavior. The dependent artifact
below closes the three callback-side helper bodies without expanding the base
factory claim. A second dependent artifact closes the distinct initializer as
its own offset-only tranche.

Finally, an exhaustive operand scan of all 25,490 atlas ranges, 3,735,718
bytes, and 1,153,814 decoded instructions finds exactly two references to the
two callback VAs: immediate closure producers at `0x002e6b9b` and
`0x002ec322`. Direct calls, comparisons, absolute-memory references, and other
immediate uses are empty. Structural and exact tests tamper prerequisite joins,
publication/return witnesses, literals, reviewed instruction points, sealed
CFG paths and register writers, staged IAT/stage/call/path facts, ungrouped
register calls, native edges, target records/scope/aggregates, method and
summary fields, schema fields, and immutable-output protections.

## Dependent class-return helper artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_return_helper_chain.json`
has analysis kind `pe_native_lua_class_return_helper_chain`. It canonical-pins
the exact factory artifact above, then seals helpers `0x002eb140`, `0x002eb560`,
and `0x002ec050`: three bodies / 501 bytes and three CFGs / 190 nodes / 201
edges. Its pretty-printed file SHA-256 is
`aab9847af280484af26885f6390f586726fd173466b76d5f0b2cda104f836bec`;
its canonical JSON SHA-256 is
`33ad87a98131700dce12bd34a7febea3159b6f461710f0b8296d95ded1b37095`.

The marker helper exact-reads `__luabind_classrep`, distinguishes the
no-metatable arm, performs a metamethod-capable `lua_gettable` lookup, converts
the result with `lua_toboolean`, and restores the prior stack on both normal
metatable arms through `lua_settop(-3)`. This is a marker-field truth test, not
a raw lookup, native type proof, or class-identity proof.

The two-value helper iterates the second entry value through `lua_next`, skips
keys equal to exact literals `__init` and `__finalize`, and otherwise requests
`lua_settable` into the first entry value at stack index `-5`. The normalized
trace preserves the iterator key and the two entry values on normal exhaustion;
it does not claim raw assignment, metamethod absence, valid table inputs, or
successful execution.

The mutation helper remains deliberately field-level. It seals the argument
`+4` assertion arm, traversal rooted at `[argument+4]+0x34`, both per-node
native calls, the `+0x14` word copy, the internal-alias and external-input
branches, both capacity-helper calls, two-word copy variants, and the final
eight-byte append advance. No class, inheritance, relationship, container,
ownership, or callee-behavior names are assigned.

Across the three bodies the artifact joins all 14 direct Lua calls and all six
EBX/EDI staged calls under a complete eight-encoding `call r32` audit. It also
retains six outgoing native-call sites to five exact targets and re-reads all
three helper literals from non-writable `.rdata`. An exhaustive scan of all
25,490 atlas ranges, 3,735,718 bytes, and 1,153,814 instructions finds exactly
six helper-entry references, all immediate `E8` calls: five from returned
callback `0x002ec110` and the explicit alternate
`0x002e7970 -> 0x002eb140` call at `0x002e7ce0`. Comparisons, absolute-memory
operands, and other direct-address uses are empty. The alternate caller remains
reference-only; its 1,348-byte body is not folded into this helper artifact.

The factory-side initializer `0x002eacf0` remains separate from this helper
artifact and is normalized by the adjacent artifact below.

## Dependent class-initializer artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_initializer_chain.json`
has analysis kind `pe_native_lua_class_initializer_chain`. It canonical-pins
the exact factory artifact and retains its conditional initializer edge, then
seals the single `0x002eacf0` body: 612 bytes and one 185-node / 191-edge CFG.
Its pretty-printed file SHA-256 is
`8bd9b4ad928675f0cb2e708ec6695daf1618dfbd3eff1324f8bfa7147bc9a4b2`;
its canonical JSON SHA-256 is
`799ab272966a317f27c0fbaf25df7d47821650a6f5e0b1a914c98eb40dcfece9`.

The artifact preserves only fixed-offset grammar. It records the initial
writes through `+0x44`, three state/reference pairs, each prior-reference guard,
the `__luabind_classes` lookup and `+0x0c` assertion arm, the `+0x10`
`lua_rawgeti` input, and the later `+0x30`, `+0x40`, and `+0x44` stores. It
joins all 20 direct Lua calls and six EBX-staged calls under a complete
eight-encoding `call r32` audit. Exact literals `__luabind_classes`,
`__luabind_cast_graph`, and `__luabind_class_id_map` are re-read from
non-writable `.rdata`; the calls to `0x0007c600` and the assertion helper remain
opaque outgoing edge facts.

The all-operand atlas scan covers 25,312 functions, 25,490 ranges, 3,735,718
bytes, and 1,153,814 instructions. Its sole initializer-entry reference is the
factory's immediate `E8` call at `0x002ec302`; comparisons, absolute-memory
operands, and other direct-address uses are empty. Runtime invocation, valid
Lua states or registry values, raw `lua_gettable` behavior, successful calls,
assertion termination, ownership, lifetime, indirect consumers, and source
class or vtable equivalence remain unproved.

## Dependent self-linked-record helper artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_self_linked_record_helper_chain.json`
has analysis kind `pe_native_self_linked_record_helper_chain`. It
canonical-pins the exact class-initializer artifact and rejoins its
`0x002ead8b -> 0x0007c600` edge, then seals the 41-byte helper body and its
16-node / 18-edge CFG. Its pretty-printed file SHA-256 is
`50786d8c2b84702c3d0c246c90ee715afa7c7ef544ddf3fc8afb66e487a01d3c`;
its canonical JSON SHA-256 is
`994b4af188a8017d0dce172a53a9598b9cdf7a48d2faef1fbcbfa5ffcbbf2ddb`.

The exact body pushes immediate `24` before the sole direct native call, whose
program-facts target carries the analysis label `operator_new` at
`0x003574db`. The returned EAX is retained syntactically; the body conditionally
stores it at offsets `+0`, `+4`, and `+8` under the exact EAX, EAX-plus-four,
and EAX-plus-eight tests, then writes word `0x0101` at `+0x0c`. In particular,
the latter two tests are not normalized into ordinary returned-EAX null
guards. The symbol label and size immediate do not establish successful
allocation, a valid or writable result, or a source-level record type.

The all-operand atlas scan covers all 25,312 functions, 25,490 ranges,
3,735,718 bytes, and 1,153,814 instructions. Exactly nine helper-entry
references survive, all immediate `E8` calls from nine distinct owners;
comparison, absolute-memory, and other direct-address partitions are empty.
For each owner the artifact seals one bounded window containing adjacent
`+0` / `+4` zero stores, the helper call, and a returned-EAX store after zero
to two intervening decoded instructions. The caller bodies and CFGs remain
reference-only. Runtime reachability, normal return, allocation or caller
success, pointer validity, aliasing, tree/container/sentinel identity,
ownership, lifetime, computed references, indirect calls, and Lua-side
consumers remain unproved.

## Dependent assertion-helper static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_static_boundary.json`
has analysis kind `pe_native_assertion_helper_static_boundary`. It
canonical-pins the exact class-initializer artifact and rejoins its remaining
`0x002eae76 -> 0x00379cc2` edge. The artifact seals the 72-byte target body,
all 29 exact instruction points, and its 29-node / 30-edge CFG. Its
pretty-printed file SHA-256 is
`7fd6879c031ba4e665024789f3cbf9308c49ea3c649ca300b441ada38d9ade5e`;
its canonical JSON SHA-256 is
`beeebb2dadd0ef2a77742f9296760fd09afe5c566c7b46bf36d2dd3cf8e441b4`.

The predecessor window records only exact syntax: the initializer's sentinel
comparison and branch, immediate `96`, two pointers into non-writable
`.rdata`, and the direct helper call. The helper body has no direct Lua call,
staged Lua dispatch, `call r32`, or retained literal. Its four outgoing direct
calls remain opaque native edges, and the trailing `int3` does not prove
termination.

The all-operand atlas scan covers all 25,312 functions, 25,490 ranges,
3,735,718 bytes, and 1,153,814 instructions. Exactly 881 helper-entry
references survive from 660 owners; every one is a five-byte immediate `E8`
call. Comparison, absolute-memory, and other direct-address partitions are
empty. Runtime reachability, invocation order or frequency, argument validity,
CRT identity or ownership, dialog/display behavior, normal return, abort,
termination, source equivalence, computed or indirect references, un-atlased
code, and Lua-side references remain unproved.

## Dependent operator-new static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_static_boundary.json`
has analysis kind `pe_native_operator_new_static_boundary`. It
canonical-pins the exact self-linked-record helper artifact and rejoins its
`0x0007c602 -> 0x003574db` edge. The join is also checked against the current
independently rebuilt whole-atlas reference record, including instruction,
source-atlas, target-atlas, immediate-`E8`, and normalized Ghidra-edge identity.

The artifact seals the 51-byte target body, all 20 exact instruction points,
and its 20-node / 22-edge CFG. Four outgoing direct calls remain opaque native
edges. The body contains no direct Lua call, staged Lua dispatch, `call r32`,
or retained literal. Its pretty-printed file SHA-256 is
`08cfc38143f47c4b4f737e4638f82495b5bfd22341626a1ee3d7ea66df2005e9`;
its canonical JSON SHA-256 is
`d0cecf29ab94b05dbe8f75c2c6edd823b83c53ed06f853d4db478a76e046479f`.

The all-operand atlas scan covers all 25,312 functions, 25,490 ranges,
3,735,718 bytes, and 1,153,814 instructions. Exactly 1,233 target-entry
references survive from 1,050 owners. Of these, 1,232 are five-byte immediate
`E8` calls; the sole other-address reference is a declared `E9` instruction at
`0x00357874`. Comparison and absolute-memory partitions are empty. The
`operator_new` name is an analysis label only. Allocation semantics, ABI,
success, ownership, lifetime, size meaning, runtime reachability, normal
return, source identity, opaque-callee behavior, computed or indirect
references, data references, un-atlased code, and Lua-side references remain
unproved. Publication proves one locked point-in-time snapshot; a published
destination that fails validation is preserved for inspection rather than
deleted.

## Dependent callnewh static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_callnewh_static_boundary.json`
has analysis kind `pe_native_callnewh_static_boundary`. It canonical-pins the
exact operator-new artifact and rejoins its
`0x003574e3 -> 0x0038bbc4` edge. The join is independently checked against the
current whole-atlas reference record, including instruction, source/target
atlas, immediate-`E8`, and normalized Ghidra-edge identity.

The artifact seals the 68-byte target body, all 30 exact instruction points,
and its 30-node / 31-edge CFG. It retains opaque direct edges
`0x0038bbd5 -> 0x0038bc08` and `0x0038bbff -> 0x003574ca`. It also records an
unresolved absolute-memory call at `0x0038bbe5` through VA `0x007d6580` / RVA
`0x003d6580`, verified in non-writable `.rdata`; an unresolved `call ESI` at
`0x0038bbeb`; and an absolute read at `0x0038bbca` from VA `0x00893f28` / RVA
`0x00493f28`, verified in writable `.data`. Direct and staged Lua calls and
retained literals are empty. The complete eight-register call audit contains
only the ESI site.

The all-operand atlas scan covers all 25,312 functions, 25,490 ranges,
3,735,718 bytes, and 1,153,814 instructions. Exactly four target-entry
references survive from four owners, all five-byte immediate `E8` calls;
comparison, absolute-memory, and other-address reference partitions are empty.
The artifact's pretty-printed file SHA-256 is
`5b1651f4b17b3d6531b71a19c828ab4700cebb19f444c5db6d694e5534793449`;
its canonical JSON SHA-256 is
`27f7495174094b3d6dca6acd6e9975a4dfa7d349f3bf974d40c3f5acd0b4eb45`.

The `__callnewh` spelling remains an analysis label only. Allocation,
new-handler, ABI, success, ownership, lifetime, size meaning, direct- or
indirect-callee identity or behavior, normal return, runtime reachability,
dynamic-target resolution, source equivalence, data consumers, un-atlased
code, and Lua-side references remain unproved.

## Dependent query-new-handler static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_static_boundary.json`
has analysis kind `pe_native_query_new_handler_static_boundary`. It
canonical-pins the exact callnewh artifact and rejoins its sole
`0x0038bbd5 -> 0x0038bc08` edge. The join is independently checked against the
fresh whole-atlas reference record, including instruction, source/target
atlas, immediate-`E8`, and normalized Ghidra-edge identity.

The artifact seals the 70-byte target body, all 19 exact instruction points,
and its 19-node / 18-edge CFG. It retains four opaque direct native edges:
`0x0038bc0f -> 0x003584b0`, `0x0038bc1a -> 0x00388bc5`,
`0x0038bc41 -> 0x0038bc51`, and `0x0038bc48 -> 0x003584f6`. It also records
the absolute pointer push at `0x0038bc0a` into non-writable file-backed
`.rdata`, the absolute read at `0x0038bc24` from writable file-backed `.data`,
and the absolute read at `0x0038bc2f` from the writable virtual-only tail of
`.data`. Pointer contents and runtime values remain opaque.

The all-operand atlas scan covers all 25,312 functions, 25,490 ranges,
3,735,718 bytes, and 1,153,814 instructions. Exactly one target-entry
reference survives from one owner, a five-byte immediate `E8` call;
comparison, absolute-memory, and other-address reference partitions are empty.
Direct and staged Lua calls, the complete eight-register call audit, and
retained literals are empty. The artifact's pretty-printed file SHA-256 is
`a0e4913c271166ee3ebd0e429f86161d47f9108c5201d2de6d4219bae8b85263`;
its canonical JSON SHA-256 is
`742e341a855de34731177afd53b385c67fbd64f3d277fedf8ba6c8e9bbf61705`.

The `__query_new_handler`, SEH, lock, and security spellings remain analysis
metadata only. Handler or allocation behavior, pointer contents, ABI, success,
ownership, lifetime, source identity, direct-callee behavior, normal return,
runtime reachability, computed or indirect references, data consumers,
un-atlased code, and Lua-side references remain unproved.

## Dependent query local-helper static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_new_handler_local_helper_static_boundary.json`
has analysis kind
`pe_native_query_new_handler_local_helper_static_boundary`. It canonical-pins
the exact query-new-handler artifact and rejoins its
`0x0038bc41 -> 0x0038bc51` edge. The join is independently checked against the
whole-atlas reference record, including exact instruction, source/target
atlas, immediate-`E8`, and normalized Ghidra-edge identity.

The artifact seals the complete 9-byte target body, all four exact instruction
points, and its 4-node / 3-edge CFG. Its sole outgoing direct native edge,
`0x0038bc53 -> 0x00388c0d`, remains opaque. The whole-atlas scan covers all
25,312 functions, 25,490 ranges, 3,735,718 bytes, and 1,153,814 instructions;
exactly one target-entry reference survives from one owner, a five-byte
immediate `E8` call. Comparison, absolute-memory, other-address, direct/staged
Lua, complete `call r32`, retained-literal, and absolute-address partitions
are empty.

The artifact's pretty-printed file SHA-256 is
`3cc19d7a2fb7aac636aba2395692598dad8de7e51c5be9a12c75c30b33eb306c`;
its canonical JSON SHA-256 is
`01a03401fdbef4e6d1d575ab74e498b5271387a1ffde440c0dee44b28ad5439c`.
The default `FUN_0078bc51` label and the callee's analysis label remain
metadata only. Helper purpose, unlock or lock semantics, ABI, argument
meaning, success, state mutation, normal return, runtime reachability, source
identity, callee behavior, dynamic or computed references, data consumers,
un-atlased code, and Lua-side references remain unproved.

## Dependent relationship-defined callee static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_local_helper_callee_static_boundary.json`
has analysis kind `pe_native_query_local_helper_callee_static_boundary`. It
canonical-pins the local-helper artifact and rejoins its sole native edge,
`0x0038bc53 -> 0x00388c0d`, against the independently rebuilt whole-atlas
reference row. The join includes the exact instruction size and SHA-256,
source and target atlas identities, immediate-`E8` form, and normalized Ghidra
edge.

The artifact seals the complete 23-byte target body, all nine instruction
points, and its 9-node / 8-edge CFG. The body contains no direct native edge,
direct or staged Lua call, `call r32`, or retained literal. Its complete entry
scan covers all 25,312 functions, 25,490 ranges, 3,735,718 bytes, and
1,153,814 instructions. Exactly 29 references from 29 owners survive, all
five-byte immediate `E8` calls; comparison, other-address, and
absolute-memory entry-reference partitions are empty.

Two absolute operand-syntax records remain. The add at `0x00388c16` names VA
`0x008b70a8` / RVA `0x004b70a8` in the virtual-only writable `.data` tail.
The indirect call at `0x00388c1c` names VA `0x007d6080` / RVA `0x003d6080`
in file-backed non-writable `.rdata`. The sealed PE import table has exactly
one matching row: `KERNEL32.dll!LeaveCriticalSection`, hint 825, with no
ordinal. This is exact import-table metadata; it does not prove the call
executes or assign synchronization behavior to the enclosing function.

The artifact's pretty-printed file SHA-256 is
`2a0f26e367e6527890757e7fdafa9f621e3a0b07566fd7624807a5781b44ef95`;
its canonical JSON SHA-256 is
`c41457569fcc4f412c35de53f7830d6e4049791a4991062d341d73a756437310`.
Publication validates one locked point-in-time snapshot, normalizes inherited
errors, blocks writer contention, preserves an existing published destination
after failed final validation, and removes a failed private publication. The
`___acrt_unlock` spelling remains analysis metadata only. Purpose,
lock/unlock or synchronization semantics, ABI, argument meaning, state
mutation, success, normal return, runtime reachability, source identity,
pointed-to data, dynamic or computed references, data consumers, un-atlased
code, and Lua-side references remain unproved.

## Dependent query-handler second-callee static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_second_callee_static_boundary.json`
has analysis kind `pe_native_query_handler_second_callee_static_boundary`. It
canonical-pins the query-handler artifact and rejoins direct edge
`0x0038bc1a -> 0x00388bc5` against the independently rebuilt entry-reference
row. The join pins exact instruction size and SHA-256, source and target atlas
identities, immediate-`E8` form, and the normalized Ghidra edge.

The artifact seals the complete 23-byte target body, all nine instruction
points, and its 9-node / 8-edge CFG. It has no direct native edge, direct or
staged Lua call, `call r32`, or retained literal. The whole-atlas scan covers
25,312 functions, 25,490 ranges, 3,735,718 bytes, and 1,153,814 instructions.
Exactly 26 target-entry references from 26 owners survive, all five-byte
immediate `E8` calls; comparison, other-address, and absolute-memory
entry-reference partitions are empty.

The add at `0x00388bce` names VA `0x008b70a8` / RVA `0x004b70a8` in the
virtual-only writable `.data` tail. The indirect call at `0x00388bd4` names
VA `0x007d6084` / RVA `0x003d6084` in file-backed non-writable `.rdata`. The
sealed PE import table has exactly one matching row:
`KERNEL32.dll!EnterCriticalSection`, hint 238, with no ordinal. This remains
exact import-table metadata and proves neither runtime execution nor the
enclosing function's synchronization behavior.

The artifact's pretty-printed file SHA-256 is
`39daf451a37440201d5cadedf946da30d3fa90e1a23677bf39f913f4a8fa6d33`;
its canonical JSON SHA-256 is
`fd8836f3ccaa14ec45931d611f96122b7b64f2ca54331d6aa2730197c1f45b20`.
Publication validates one locked point-in-time snapshot, rejects writer
contention, normalizes inherited errors, preserves existing published
evidence after failed final validation, and removes a failed private
publication. The `___acrt_lock` analysis label and named import do not prove
purpose, lock or synchronization semantics, ABI, argument meaning, state
mutation, success, normal return, runtime reachability, source identity,
pointed-to data, dynamic or computed references, data consumers, un-atlased
code, or Lua-side references.

## Explicit nonclaims

This survey does not prove that `class` is globally available at runtime, that
the string is a source-level class name, that allocation or initialization
succeeds, that setters/raw getters have the intended values, that the two
userdata objects have any particular native type or relationship, that registry
references remain valid, that helper calls return normally, or that the chain
covers indirect/dynamic/Lua-level consumers and mutations.
