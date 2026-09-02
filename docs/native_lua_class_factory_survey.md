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
calls are retained as opaque native edges, and the trailing `int3` does not
prove termination. The first and second direct targets are now closed below;
the other two remain separate opaque boundaries.

The all-operand atlas scan covers all 25,312 functions, 25,490 ranges,
3,735,718 bytes, and 1,153,814 instructions. Exactly 881 helper-entry
references survive from 660 owners; every one is a five-byte immediate `E8`
call. Comparison, absolute-memory, and other direct-address partitions are
empty. Runtime reachability, invocation order or frequency, argument validity,
CRT identity or ownership, dialog/display behavior, normal return, abort,
termination, source equivalence, computed or indirect references, un-atlased
code, and Lua-side references remain unproved.

## Dependent assertion-helper first-callee static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_static_boundary.json`
has analysis kind
`pe_native_assertion_helper_first_callee_static_boundary`. It canonical-pins
the exact assertion-helper receipt and rejoins its
`0x00379ccd -> 0x0038e392` edge. The independently rebuilt entry-reference row
pins the instruction bytes and SHA-256, owner and target atlas identities,
immediate-`E8` form, and normalized Ghidra-edge identity.

The artifact seals exact atlas range `[0x0038e392,0x0038e3d1)`: 63 bytes, all
23 exact instruction points, and its 23-node / 23-edge CFG. Its three `ret`
instructions are terminal CFG syntax only. The complete outgoing-native
partition contains two opaque edges, `0x0038e3bc -> 0x00385bcc` and
`0x0038e3c7 -> 0x00379ef2`. Direct/staged Lua calls, indirect controls, all
eight `call r32` forms, BND-prefixed controls, segment-qualified memory, and
interrupt syntax are empty.

Three absolute-memory operands at `0x0038e3a8`, `0x0038e3af`, and
`0x0038e3b4` all name VA `0x008b7534` / RVA `0x004b7534`. The RVA lies in
writable `.data` but beyond its raw-backed end, so it is virtual-only and has
no file offset. The exact PE base-relocation directory is hash-pinned and
contains matching HIGHLOW sites at `0x0038e3a9`, `0x0038e3b0`, and
`0x0038e3b6`. Four non-control immediates (`2`, `3`, `0x16`, and
`0xffffffff`) remain opaque syntax.

The all-operand atlas scan covers all 25,312 functions, 25,490 ranges,
3,735,718 bytes, and 1,153,814 instructions. Exactly one target-entry
reference survives: the parent five-byte immediate `E8` call at
`0x00379ccd`, from one owner. Comparison, other-address, and absolute-memory
entry-reference partitions are empty. The artifact's pretty-printed file
SHA-256 is
`bc6e195e133fba208b13344aea8e211e44fc57e0399d860af38f2ab9ed3383f0`;
its canonical JSON SHA-256 is
`e99d2b76879c1456c6ec44bf3fcbc38f2f50a456aae6416687f0cf1f09898da0`.

The `__set_error_mode`, `__errno`, and default Ghidra spellings remain analysis
metadata only. CRT identity, source purpose, ABI, arguments, outputs, global
state, runtime reachability, ordering, effects, success, failure, normal
return, and child behavior remain unproved.

## Dependent assertion-helper first-callee direct-callee pair artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_static_boundary.json`
has analysis kind
`pe_native_assertion_helper_first_callee_direct_callee_pair_static_boundary`.
It canonical-pins the first-callee receipt and rejoins both of its exact opaque
parents: `0x0038e3bc -> 0x00385bcc` and
`0x0038e3c7 -> 0x00379ef2`. Each join also matches the independently rebuilt
all-atlas reference row on instruction bytes and SHA-256, source/owner and
target atlas identities, immediate-`E8` form, and normalized declared-edge
identity.

The paired artifact seals two complete single-range bodies. Target
`0x00385bcc` spans `[0x00385bcc,0x00385bdf)`: 19 bytes, seven instructions,
and a 7-node / 6-edge CFG. Target `0x00379ef2` spans
`[0x00379ef2,0x00379f02)`: 16 bytes, nine instructions, and a 9-node / 8-edge
CFG. The complete outgoing-native partitions retain one opaque child each,
`0x00385bcc -> 0x0038edb6` and `0x00379ef9 -> 0x00379e77`. Direct/staged Lua,
indirect and register controls, import/IAT body controls, BND-prefixed,
segment-qualified, and interrupt syntax are empty.

The exact immediate at `0x00385bd5` names VA `0x008940d0` / RVA
`0x004940d0` in raw-backed writable `.data`, at file offset `0x004922d0`.
The hash-pinned relocation directory contains the sole matching HIGHLOW site
at `0x00385bd6`; the second target has none. Ordinary immediates `0x10` and
`0x14` remain opaque syntax.

The all-operand atlas scan covers all 25,312 functions, 25,490 ranges,
3,735,718 bytes, and 1,153,814 instructions. Exactly 479 references survive,
all five-byte immediate `E8` calls: 308 references from 202 owners to
`0x00385bcc`, and 171 from 148 owners to `0x00379ef2`. Their union has 202
unique owners and 350 target-owner pairs. The artifact's pretty-printed file
SHA-256 is
`40a83312f9867bcf385e836eb9547398803d8628a29c3d4716aec7ba4c21a493`;
its canonical JSON SHA-256 is
`e1a04d9e847b1ec61e57e24cb02c03eea6b35aae5a1ad059cdd4339ebb939378`.

The `__errno` and default Ghidra names remain metadata only. CRT identity,
source purpose, ABI, input/output meaning, `.data` contents, runtime
reachability, effects, success, failure, normal return, and both child
behaviors remain unproved.

## Dependent direct-callee pair first-target child artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary.json`
has analysis kind
`pe_native_assertion_helper_first_callee_direct_callee_pair_first_target_child_static_boundary`.
It canonical-pins the paired predecessor and rejoins its exact
`0x00385bcc -> 0x0038edb6` edge. The parent row is also present in the
independently rebuilt whole-atlas reference frontier.

The artifact seals `[0x0038edb6,0x0038ee3b)`: 133 bytes, all 53 instruction
points, and a 53-node / 57-edge CFG. Its complete outgoing-native partition
contains six opaque direct edges at `0x0038edd0`, `0x0038ede2`, `0x0038edf0`,
`0x0038edff`, `0x0038ee11`, and `0x0038ee17`. Direct/staged Lua calls,
register calls, other indirect controls, BND-prefixed controls,
segment-qualified memory, and interrupt syntax are empty.

The body contains three absolute-IAT `FF 15` controls. Raw PE import syntax
binds `0x007d6114` to metadata spelling `GetLastError` and `0x007d60dc` to
metadata spelling `SetLastError`; no external IAT-consumer closure or runtime
meaning is claimed. Absolute-memory operands at `0x0038edc5` and `0x0038edf9`
name raw-backed writable `.data` VA `0x00894290` / RVA `0x00494290`, file
offset `0x00492490`. The immediate at `0x0038ee0b` names virtual-only writable
`.data` VA `0x008b7550` / RVA `0x004b7550` and has no file offset. The
hash-pinned relocation directory contains all six corresponding HIGHLOW sites.
Four non-PE immediates (`0xffffffff`, `0x364`, `1`, and `0xc`) remain opaque
comparison/data syntax.

The all-operand scan covers all 25,312 functions, 25,490 ranges, 3,735,718
bytes, and 1,153,814 instructions. Exactly six target-entry references survive
from six owners, all five-byte immediate `E8` calls. The artifact's
pretty-printed file SHA-256 is
`eac8de889925d07bc807f1ec676c143348d2729bc51d6ecbc402f08ca2ef3eab`;
its canonical JSON SHA-256 is
`314c5817e3a1560c446853474cc0f86fbf3a8195fb60f48c85822a3ed8aca3bc`.

The `___acrt_getptd_noexit`, `GetLastError`, and `SetLastError` spellings are
analysis/import metadata only. CRT identity, source purpose, ABI, inputs,
outputs, data or IAT contents, runtime reachability, effects, success,
failure, normal return, and all six child behaviors remain unproved. The
paired predecessor's second child at `0x00379e77` remains opaque.

## Dependent assertion-helper second-callee static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_second_callee_static_boundary.json`
has analysis kind
`pe_native_assertion_helper_second_callee_static_boundary`. It canonical-pins
the exact assertion-helper receipt and rejoins its
`0x00379cdc -> 0x0038c89f` edge. The independently rebuilt entry-reference row
pins instruction bytes and SHA-256, owner and target atlas identities,
immediate-`E8` form, and normalized Ghidra-edge identity.

The artifact seals the complete six-byte target body, both exact instruction
points, and its 2-node / 1-edge CFG. The last one-byte `ret` is represented as
`terminal` with no successor; this proves syntax only, not normal return. The
declared outgoing-native, indirect-control, direct/staged Lua, complete
eight-register call, non-PE-immediate, BND-prefixed, segment-qualified, and
interrupt partitions are all empty.

The sole PE-address operand is operand 1 of the five-byte `A1` read at
`0x0038c89f`: VA `0x008b7318` / RVA `0x004b7318`. It lies within writable
`.data` (section RVA `0x00492000`, virtual size `0x000471cc`, raw size
`0x00024800`) but beyond the section's raw-backed end, so it is explicitly
virtual-only with no file offset. The receipt does not read or assign meaning
to its runtime contents.

The all-operand atlas scan covers all 25,312 functions, 25,490 ranges,
3,735,718 bytes, and 1,153,814 instructions. Exactly three target-entry
references survive from three owners, all five-byte immediate `E8` calls at
`0x00379cdc`, `0x00392d68`, and `0x00392f34`. Comparison, other-address, and
absolute-memory entry-reference partitions are empty. The artifact's
pretty-printed file SHA-256 is
`d9ae877fc1f9acb604a566470d0b8c2c1bb471701ef19de0e7c0a170e1287a07`;
its canonical JSON SHA-256 is
`ad26b7dddb2996fd69b53937de0ae8bdb6d694982df62c280c4a03430895e0d7`.

The default `FUN_0078c89f` name is analysis metadata only. Source purpose,
ABI, inputs, outputs, state mutation, `.data` contents, runtime reachability,
effects, success, failure, and normal return remain unproved. With no outgoing
native edge, this relationship-defined branch ends here.

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

## Dependent operator-new second-callee static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_second_callee_static_boundary.json`
has analysis kind
`pe_native_operator_new_second_callee_static_boundary`. It canonical-pins the
exact operator-new receipt and rejoins its
`0x003574f3 -> 0x0035848f` edge. The join is independently rebuilt from the
whole atlas and pins instruction bytes and SHA-256, source and target atlas
identities, immediate-`E8` form, and normalized Ghidra-edge identity.

The artifact seals the complete 28-byte target body, all nine instruction
points, and its 9-node / 8-edge CFG. It retains two opaque outgoing direct
edges: `0x00358498 -> 0x00358477` and
`0x003584a6 -> 0x00370dab`. Because the second direct call ends the declared
range, its final node is `direct_call_range_end`; this is a boundary fact, not
a return or callee-behavior claim. The complete PE-address operand partition
contains those two `.text` targets and the non-writable file-backed `.rdata`
immediate VA `0x0088c9d4` / RVA `0x0048c9d4` pushed at `0x0035849d`.

The all-operand atlas scan covers all 25,312 functions, 25,490 ranges,
3,735,718 bytes, and 1,153,814 instructions. Exactly one target-entry
reference survives from one owner: the five-byte immediate `E8` parent call at
`0x003574f3`. Comparison, absolute-memory, and other-address reference
partitions are empty. Direct and staged Lua calls, all eight register-call
partitions, indirect controls, BND-prefixed controls, segment-qualified memory
syntax, and interrupt syntax are also empty. The artifact's pretty-printed
file SHA-256 is
`c427f25ed77f605911ddea747fcda26b44814ca0060f0c4fce3bbffcfe717f25`;
its canonical JSON SHA-256 is
`ebc3514d67711d7774e51eecd4c881f9826ed6ec68f40ca462415e654ba7d856`.

The default `FUN_0075848f` name is analysis metadata only. Source purpose,
ABI, exception behavior, argument or pointer meaning, normal return, runtime
reachability, source equivalence, callee behavior, computed or indirect
references, data consumers, un-atlased code, and Lua-side references remain
unproved. Both outgoing callees are now closed by the dependent artifacts
below.

## Dependent operator-new second-callee first-callee static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_second_callee_first_callee_static_boundary.json`
has analysis kind
`pe_native_operator_new_second_callee_first_callee_static_boundary`. It
canonical-pins the exact second-callee receipt and rejoins its
`0x00358498 -> 0x00358477` edge. The independently rebuilt whole-atlas row
pins the instruction bytes and SHA-256, owner and target atlas identities,
immediate-`E8` form, and normalized Ghidra-edge identity.

The artifact seals the complete 24-byte target body, all six instruction
points, and its 6-node / 5-edge CFG. The last `ret` is represented as
`terminal` with no successor; this is a syntactic boundary, not proof of normal
return. The declared outgoing-native, indirect-control, direct and staged Lua,
all eight register-call, BND-prefixed, segment-qualified, and interrupt
partitions are empty. Two exact immediate operands name non-writable
file-backed `.rdata`: VA `0x007f1a0c` / RVA `0x003f1a0c` at `0x00358481`,
and VA `0x007f1a04` / RVA `0x003f1a04` at `0x00358488`. Their contents remain
opaque. The zero immediates at `0x00358477` and `0x0035847d` are retained in a
separate complete non-PE-literal partition.

The all-operand atlas scan covers all 25,312 functions, 25,490 ranges,
3,735,718 bytes, and 1,153,814 instructions. Exactly one target-entry
reference survives from one owner: the five-byte immediate `E8` parent call at
`0x00358498`. Comparison, absolute-memory, and other-address reference
partitions are empty. The artifact's pretty-printed file SHA-256 is
`7837f58f2f0b08968e29d42cb0e6da4aa405962e12b8ce956c9c8be187d2abc8`;
its canonical JSON SHA-256 is
`a82567f379b942b53f80b1f739a488e7de2637ea39e318f7a928af37900ae262`.

The default `FUN_00758477` name is analysis metadata only. Source purpose,
ABI, inputs, outputs, state mutation, `.rdata` contents, runtime reachability,
normal return, source equivalence, data consumers, un-atlased code, and
Lua-side references remain unproved. Because the body has no outgoing native
edge, this relationship-defined branch ends here.

## Dependent operator-new second-callee second-callee static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_operator_new_second_callee_second_callee_static_boundary.json`
has analysis kind
`pe_native_operator_new_second_callee_second_callee_static_boundary`. It
canonical-pins the exact second-callee receipt and rejoins its
`0x003584a6 -> 0x00370dab` edge. The independently rebuilt whole-atlas row pins
the instruction bytes and SHA-256, owner and target atlas identities,
immediate-`E8` form, and normalized Ghidra-edge identity.

The artifact seals the complete 110-byte target body, all 45 instruction
points, and its 45-node / 48-edge CFG. Its sole declared outgoing direct call,
`0x00370de0 -> 0x003581b3`, is canonical-joined to the already sealed body and
CFG in the residual-direct-target-set receipt. Two indirect controls remain
opaque: register call `ESI` at `0x00370de5` and absolute-memory `FF 15` at
`0x00370e0a`. The latter reads VA `0x007d616c` / RVA `0x003d616c` from
non-writable file-backed `.rdata`.

The raw PE import proof binds that slot to descriptor index 7 and thunk index
91, exact matching ILT/IAT words, both array terminators, hint 945, and the
unique parsed `KERNEL32.dll` / `RaiseException` row. This is metadata only and
does not prove the imported call executes or assign it behavior. The complete
address partition contains six immediate `.text`/`.rdata` operands and that
one absolute-memory IAT operand. Seven other immediates form a separate non-PE
partition. The exact `F3 A5` instruction at `0x00370dc2` is retained as one
`ES:[EDI]` segment-qualified write syntax. Direct/staged Lua, BND-prefixed, and
interrupt partitions are empty; the eight-register audit contains only the
one ESI call.

The all-operand entry scan covers all 25,312 functions, 25,490 ranges,
3,735,718 bytes, and 1,153,814 instructions. Exactly 481 target-entry
references from 414 owners survive, all immediate `E8` calls. An independent
traversal over the same scope finds exactly three absolute-memory `FF 15` uses
of the IAT slot from three owners. The artifact's pretty-printed file SHA-256
is `e2b04a14adfa5440a1b01f978b8785a48b3f7cf6ed26d59577963a48d4eef365`;
its canonical JSON SHA-256 is
`87f650968e7858d1676b51a99b98822846db39577da2ef737d9e8d74f4c251a8`.

The `__CxxThrowException@8`, library, and import names are analysis/import
metadata only. Source identity, ABI, input/output meaning, exception or throw
behavior, runtime reachability, ordering, state mutation, imported-function
execution, effects, and normal return remain unproved. The one direct child is
already sealed, so this relationship-defined branch ends here and both direct
children of the operator-new second callee are closed.

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

## Dependent query-handler first-callee static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_static_boundary.json`
has analysis kind `pe_native_query_handler_first_callee_static_boundary`. It
canonical-pins the query-handler artifact and rejoins direct edge
`0x0038bc0f -> 0x003584b0` against the independently rebuilt entry-reference
row. The join pins exact instruction bytes, size, and SHA-256; source and
target atlas identities; immediate-`E8` form; and the normalized Ghidra edge.

The artifact seals the complete 70-byte target body, all 21 instruction
points, and its 21-node / 20-edge CFG. It has no direct native edge, direct or
staged Lua call, `call r32`, or retained literal. The whole-atlas scan covers
25,312 functions, 25,490 ranges, 3,735,718 bytes, and 1,153,814 instructions.
Exactly 66 target-entry references from 66 owners survive, all five-byte
immediate `E8` calls. Comparison, other-address, and absolute-memory
entry-reference partitions are empty.

Five exact syntax receipts remain opaque. The immediate at `0x003584b0`
names VA `0x007729b0` / RVA `0x003729b0` in file-backed non-writable `.text`.
The memory push at `0x003584b5` and destination write at `0x003584ee` use
segment-relative `FS:[0]` operands and are not represented as PE absolute
addresses. The absolute read at `0x003584cd` names VA `0x00893f28` / RVA
`0x00493f28` in file-backed writable `.data`. The final instruction at
`0x003584f4` has exact two-byte BND-prefixed-return syntax. Executable
validation derives each syntax record through Capstone; contents and runtime
meaning remain unassigned.

The artifact's pretty-printed file SHA-256 is
`f4d43affe98441996f1d10086438c93136b181665c2039b9b1ae18beb618e6b4`;
its canonical JSON SHA-256 is
`b08dc12a2f4951817e4e7c24dbdfc4afec03550c2828d7d14c1d757404517d73`.
Publication validates one locked point-in-time snapshot, rejects writer
contention, normalizes inherited errors, preserves existing published
evidence after failed final validation, and removes a failed private
publication. The `__SEH_prolog4` analysis label does not prove purpose, SEH,
prolog, exception, stack, register, security-cookie, ABI, argument meaning,
state mutation, success, normal return, runtime reachability, source identity,
operand contents, dynamic or computed references, data consumers, un-atlased
code, or Lua-side references.

## Dependent first-callee pointer-target static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_static_boundary.json`
has analysis kind
`pe_native_query_handler_first_callee_pointer_target_static_boundary`. It
canonical-pins the first-callee and query-handler artifacts and rejoins the
five-byte `PUSH imm32` at `0x003584b0`. That exact syntax names VA
`0x007729b0` / RVA `0x003729b0` in file-backed non-writable `.text`; both the
predecessor receipt and independently rebuilt all-atlas row classify it as an
opaque `other_address` use, not a direct call.

The artifact seals the complete 358-byte target body, all 120 exact instruction
points, and its 120-node / 130-edge CFG. Eleven direct native edges are joined
to exact source and target atlas records and normalized Ghidra edges, but their
semantics remain opaque. Direct and staged Lua-call partitions and retained
literals are empty. The complete `FF D0` through `FF D7` audit finds only
`call ESI` at `0x00372a71`. The `.rdata` ESI load at `0x00372a5f` is preserved
as syntax only: intervening direct call `0x00372a6c` means this static receipt
does not claim that value survives to or identifies the later register call.

Six non-control PE operand receipts remain opaque. The read at `0x003729cd`
names VA `0x00893f28` / RVA `0x00493f28` in file-backed writable `.data`.
The read at `0x00372a45`, immediate at `0x00372a4e`, and ESI-load syntax at
`0x00372a5f` name VA `0x007f2750` / RVA `0x003f2750` in file-backed
non-writable `.rdata`. The immediates at `0x00372ab9` and `0x00372ae4` name the
`.data` address. Exact operand indexes, access modes, absent memory base/index/
segment registers, section characteristics, and instruction identities are
pinned without assigning pointed-to contents or runtime behavior.

The whole-atlas scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly three entry references survive, owned by
`0x003584b0`, `0x0039d580`, and `0x0039d770`. All three are identical
five-byte immediate pushes classified as `other_address`; direct-call,
comparison, and absolute-memory target-reference partitions are empty. The
explicit three-owner partition is required during structural validation.

The artifact's pretty-printed file SHA-256 is
`0fc22f514989853df44f285396b4f59683ee94f703fcc355b566ad6518783c4d`;
its canonical JSON SHA-256 is
`41ee47debe789243dfe9fd9566958846cd79cb82549acb99eafc9e2b5cfd9349`.
Publication validates one locked point-in-time snapshot, rejects writer
contention, normalizes inherited errors, preserves existing evidence after
failed final validation, and removes a failed private publication. The
`__except_handler4` label remains analysis metadata only. Purpose, exception
or handler behavior, stack/register/security semantics, ABI, argument meaning,
state mutation, target identity, success, normal return, runtime reachability,
dynamic or computed references, data consumers, un-atlased code, and Lua-side
references remain unproved.

## Dependent adjacent-callee cluster static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary.json`
has analysis kind
`pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_static_boundary`.
It canonical-pins the pointer-target artifact and rejoins five exact parent
edges. Each parent record is independently cross-joined to its whole-atlas
reference row on instruction identity, source/owner and target atlas identity,
and normalized Ghidra edge.

The sealed span is `0x00378b3e..0x00378b9e` exclusive: 96 bytes with SHA-256
`90bbfc64c1432f6b635812d241f996137a7e02d88381c66e66955102f1f9d48d`.
It contains four distinct, exactly adjacent atlas bodies at `0x00378b3e`,
`0x00378b55`, `0x00378b6e`, and `0x00378b87`. Together they contain all 51
instruction points and four CFGs totaling 51 nodes / 47 edges. The adjacency
receipt proves layout only, not shared purpose, execution order, or semantic
kinship.

The complete outgoing direct-edge partition contains
`0x00378b5d -> 0x00378a15`, `0x00378b7d -> 0x0039cb98`, and
`0x00378b92 -> 0x00378a40`. All three edges are now closed by the dependent
receipts below, leaving no opaque declared direct edge in this cluster. The
complete `FF D0`
through `FF D7` audit finds only `call ECX` at `0x00378b4e`. Final `jmp ESI` at
`0x00378b6c` is retained as a separate opaque indirect-control record. The
exact `MOV ESI,ECX` bytes at `0x00378b57` precede an intervening direct call at
`0x00378b5d`, so this artifact does not claim that a register value survives
to or identifies the jump target.

The complete PE-address operand audit scans both immediate and absolute-memory
classes. Exactly four operand-zero immediates survive, all naming file-backed
non-writable `.text`; no absolute-memory operand survives. Three immediates
belong to the outgoing `E8` records. The opaque `PUSH` at `0x00378b77` names
VA `0x00778b82` / RVA `0x00378b82` inside the same body, without assigning its
purpose or runtime use. Direct and staged Lua evidence is empty, but the
unresolved ECX target is not thereby proved non-Lua.

The whole-atlas scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly five entry references survive, all
five-byte immediate `E8` calls from sole owner `0x003729b0`; the target
partition is `1/1/1/2` in entry order. Comparison, other-address, and
absolute-memory target-reference partitions are empty, and structural
validation requires the exact target and owner partitions.

The artifact's pretty-printed file SHA-256 is
`c7da48c159c104db62ce6f0a6c47e31e2739179d9435a49c52e2dfc3014bbaea`;
its canonical JSON SHA-256 is
`1385ca599a7442b2b18a45206619d520b19db1b5a2fa9c0ba5b54908831462a5`.
Publication validates one locked point-in-time snapshot, rejects writer
contention, normalizes inherited errors, preserves existing evidence after
failed final validation, and removes a failed private publication. Analysis
labels, adjacency, decoded registers, and address syntax do not prove purpose,
exception behavior, ABI, arguments, target identity, state mutation, success,
normal return, runtime reachability, dynamic or computed references, data
consumers, un-atlased code, or Lua-side behavior.

## Dependent adjacent-cluster second-callee static boundary

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary.json`
has analysis kind
`pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_second_callee_static_boundary`.
It canonical-pins the adjacent-cluster receipt and rejoins exact edge
`0x00378b5d -> 0x00378a15`, including the 25-byte source body, source and
target atlas identities, exact `E8` instruction, and normalized declared-edge
metadata.

The target is exactly 31 bytes at `0x00378a15`, all 16 decoded instructions,
and a 16-node / 15-edge CFG. Its `.text` backing is pinned at file offset
`0x00377e15`. The exact left atlas neighbor at `0x00378a0c` ends at the target,
and the exact right neighbor at `0x00378a34` starts at the target end; this is
layout evidence only. The body has no outgoing direct edge, direct or staged
Lua call, register call, or indirect control. The `RET 4` operand is retained
only as non-PE immediate syntax.

The sole PE-address operand is the `MOV EBX,0x00894010` immediate at
`0x00378a17`. It resolves to file-backed writable `.data` RVA `0x00494010`,
file offset `0x00492210`. The exact four bytes `20 05 93 19` and their SHA-256
are sealed, while their contents, consumers, and runtime meaning remain
opaque.

The complete all-operand atlas traversal covers 25,312 functions, 25,490
ranges, 3,735,718 bytes, and 1,153,814 instructions. Exactly four target-entry
references survive, all immediate `E8` calls at `0x003788ca`, `0x003789c7`,
`0x00378aae`, and `0x00378b5d` from four owners. The final row exactly rejoins
the cluster parent edge. The artifact's pretty-printed file SHA-256 is
`f5f42474bb049805e9844ac5cb6bffe25f4a20b8caea22ef0120620fdaabd6b8`;
its canonical JSON SHA-256 is
`ec66ae66eb932cb59f52ca3ad9095c31bb887723ed7647aef4eeeb0aaa64389d`.

The `__NLG_Notify` Ghidra name is analysis metadata only. The receipt does not
prove source identity, purpose, ABI, inputs, outputs, behavior, invocation,
effects, success, failure, termination, normal return, computed references,
un-atlased code, or Lua-side references.

## Dependent adjacent-cluster third-callee import-thunk static boundary

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary.json`
has analysis kind
`pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_third_callee_import_thunk_static_boundary`.
It canonical-pins the adjacent-cluster receipt and rejoins exact edge
`0x00378b7d -> 0x0039cb98`, including the 25-byte source body, source and
target atlas identities, exact `E8` instruction, and normalized declared-edge
metadata.

The target is exactly six bytes, one `FF 25 70 61 7d 00` instruction, and a
1-node / 0-edge CFG with `indirect_jump` flow and no successor. Its sole PE
operand is an absolute-memory read of `.rdata` VA `0x007d6170` / RVA
`0x003d6170`. The raw PE32 proof binds that slot to the unique
`KERNEL32.dll` / `RtlUnwind` named-import row with hint 1048, descriptor index
7, thunk index 92, the null descriptor at index 10, and both KERNEL32 thunk
terminators at index 139.

The complete all-operand atlas traversal covers 25,312 functions, 25,490
ranges, 3,735,718 bytes, and 1,153,814 instructions. Exactly three target-entry
references survive, all immediate `E8` calls at `0x00378889`, `0x00378913`,
and `0x00378b7d` from three owners. A separate traversal for the IAT-slot VA
finds exactly two absolute-memory reads from two owners: `FF 15` at
`0x00371024` and the target `FF 25` instruction. The artifact's pretty-printed
file SHA-256 is
`2f56d4bc7413036890013f70de5e202835f3254491048f17612a76c80a072f9b`;
its canonical JSON SHA-256 is
`1222126b3527186a823ffb252a97ddc2beb7a0c4dc49b45e15e462fb244b2a5b`.

The import and Ghidra names are metadata only. The receipt does not prove
loader resolution, unwind or exception behavior, ABI, arguments, invocation,
target execution, effects, reachability, termination, or normal return.

## Dependent adjacent-cluster fourth-callee static boundary

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary.json`
has analysis kind
`pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_static_boundary`.
It canonical-pins both the adjacent-cluster and second-callee receipts and
rejoins exact parent edge `0x00378b92 -> 0x00378a40`, including the 23-byte
source body, exact five-byte `E8`, source and target atlas identities, and
normalized declared-edge metadata.

The target is exactly 144 bytes at `0x00378a40`, all 48 decoded instructions,
and a 48-node / 51-edge CFG. Its `.text` backing is pinned at file offset
`0x00377e40`. The nearest left atlas body is the three-byte function at
`0x00378a34`; a nine-byte `CC` gap separates its end from the target. The
target ends at `0x00378ad0`, followed by a 110-byte un-atlased span and then
the 23-byte right atlas body at `0x00378b3e`. Both gaps are explicitly
unowned by the atlas and total 119 sealed bytes; this is layout evidence only.

The complete outgoing native partition has two edges. The exact
`0x00378aae -> 0x00378a15` row rejoins the pinned second-callee reference,
while `0x00378abb -> 0x00378a34` retains an opaque `FF D0 C3` child. Direct and
staged Lua calls, register calls, and other indirect controls are empty. The
receipt separately retains six non-PE immediate literals and three
FS-qualified absolute-memory forms without assigning behavior.

Nine PE-address operands survive: eight immediates and one absolute-memory
read. The latter names writable `.data` VA `0x00893f28` / RVA `0x00493f28` /
file offset `0x00492128`; its exact four bytes `4e e6 40 bb` have SHA-256
`ce27c3a226b06f760dc303582e2dd3ab690a1634fdced2e53b238a4e947cd75f`.
Every operand is file-backed and hash-pinned without a contents or runtime-use
claim.

The complete all-operand atlas traversal covers 25,312 functions, 25,490
ranges, 3,735,718 bytes, and 1,153,814 instructions. Exactly three target-entry
references survive, all immediate `E8` calls at `0x00378b92`, `0x00386e8f`,
and `0x00386fb7` from three owners. The separate endpoint scan finds one
`other_address` use: `PUSH 0x00778ad0` at `0x00378a54`, owned by the target
itself. The artifact's pretty-printed file SHA-256 is
`105170018df7456821dc09c7e762b933f490eb9544131cb94a4b8c49810669ed`;
its canonical JSON SHA-256 is
`1faeeefe0ee5d9bc9a85ad673133dc7936a02cfea50beb5cd70d72fc36bcb9c5`.

The `__local_unwind4` Ghidra name is metadata only. The receipt does not prove
source identity, purpose, unwind or exception behavior, ABI, inputs, outputs,
invocation, effects, success, failure, termination, normal return, dynamic
references, un-atlased execution, or Lua-side behavior. This closes the final
opaque declared direct edge of the adjacent cluster.

## Dependent adjacent-cluster fourth-callee child static boundary

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary.json`
has analysis kind
`pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_child_static_boundary`.
It canonical-pins the fourth- and second-callee receipts, rejoins the fourth
callee's exact `0x00378abb -> 0x00378a34` row, and requires both dependent
adjacency records to identify the same child body.

The target is exactly three bytes at `0x00378a34`: `CALL EAX; RET`. Both
instructions and the 2-node / 1-edge CFG are sealed. The register-access
frontier records that `CALL EAX` reads EAX and ESP and writes ESP, while the
plain `RET` has no explicit operand. The remaining direct-native, direct and
staged Lua, PE-address, non-PE literal, segment-qualified memory, BND,
interrupt, and explicit-return-immediate partitions are empty. This is an
opaque indirect control, not a static target claim.

Exact PE checks bind the child to non-writable file-backed `.text` at file
offset `0x00377e34`. The left atlas neighbor ends exactly at the child entry;
the child ends at a nine-byte `CC` gap, followed by the 144-byte fourth-callee
body. The gap and both neighbor bodies are hash-pinned. This proves layout and
backing only.

The complete all-operand atlas traversal covers 25,312 functions, 25,490
ranges, 3,735,718 bytes, and 1,153,814 instructions. Exactly two immediate
`E8` target-entry references survive, at `0x003789d0` and `0x00378abb`, from
owners `0x00378965` and `0x00378a40`. Both owner CFGs are sealed. The unique
predecessor of each child call loads EAX immediately from computed memory:
`[EBX+ESI*4+8]` in the first owner and `[EBX+8]` in the second. Exact paired
windows also show that EAX is reloaded after each owner's earlier call to
`0x00378a15`. No constant, relocation, absolute PE address, or import slot
proves either runtime EAX value.

The artifact's pretty-printed file SHA-256 is
`61e0571607dd92e2861f06297a410c9766135c718b0420afbf3d7351d160b570`;
its canonical JSON SHA-256 is
`71f87f861758ba8ef7f7d9a6ac435bb05df38d81e7ff5c8e7fe8c95a4fb0e193`.
The Ghidra labels, source identity, EAX value, indirect destination, ABI,
arguments, outputs, behavior, invocation, effects, success, failure,
termination, and normal return remain unproved.

## Dependent fourth-callee right un-atlased-span static boundary

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary.json`
has analysis kind
`pe_native_query_handler_first_callee_pointer_target_adjacent_callee_cluster_fourth_callee_right_unatlased_span_static_boundary`.
It canonical-pins the fourth-callee, fourth-callee-child, residual-target-set,
residual-callee, direct-call, and program-facts receipts. The fourth receipt's
exact right-gap record identifies the target range as
`[0x00378ad0,0x00378b3e)`, and its endpoint scan's sole reference is rejoined
to the new receipt's independent whole-atlas traversal.

The target is 110 exact file-backed `.text` bytes at file offset
`0x00377ed0`. A complete linear decode consumes all bytes as 34 instructions.
The receipt conservatively retains two code-candidate components rather than
declaring atlas functions: component A spans `[0x00378ad0,0x00378b16)`, 70
bytes and 21 instructions, with a 21-node / 21-edge CFG; component B spans
`[0x00378b16,0x00378b3e)`, 40 bytes and 13 instructions, with a 13-node /
12-edge CFG. Both components are locally reachable from their candidate start,
end in exact return syntax, and together form a disconnected 34-node /
33-edge union. Zero undecoded bytes are proved; whether any decoded bytes are
padding is deliberately not classified.

Four direct `E8` instructions survive: `0x00378aeb -> 0x003574ca`,
`0x00378afd -> 0x00378a40`, `0x00378b1b -> 0x00007e70`, and
`0x00378b32 -> 0x00378a40`. Atlas body identity is checked for every target.
The residual-callee receipt rejoins `0x003574ca`, the fourth-callee receipt
rejoins both calls to `0x00378a40`, and the residual-target-set receipt rejoins
`0x00007e70`. No Ghidra declared direct edge has its source, instruction, or
target inside the un-atlased range.

The complete immediate frontier contains five PE-address controls: the four
calls plus internal `JE 0x00378b15` at `0x00378ae0`. Six ordinary immediates
and explicit `RET 4` at `0x00378b3b` are partitioned separately. No absolute
memory or IAT operand, register call, other indirect control, segment-qualified
memory, BND control, interrupt, direct Lua call, or staged Lua dispatch
survives.

The exhaustive atlas operand traversal covers 25,312 functions, 25,490
ranges, 3,735,718 bytes, and 1,153,814 instructions. Exactly one reference
lands anywhere in the 110-byte span: the fourth callee's
`PUSH 0x00778ad0` at `0x00378a54`. A bytewise whole-file dword scan also finds
that address once, at file offset `0x00377e55`. The pinned base-relocation
directory proves one HIGHLOW relocation at RVA `0x00378a55`, whose entry is
`55 3a` at file offset `0x00532e08`; there is no relocation site inside the
span. The pinned import directory parses 342 named records and no ordinal
records, with no IAT slot inside the span.

The artifact's pretty-printed file SHA-256 is
`43db988b412d01cfbe06adfb258e2dfb2a3dbba98bfcf8a65e4092165a86eec1`;
its canonical JSON SHA-256 is
`02a4e933250820874a6b8876e8092636747f780bde25f28103b4585651dc0359`.
This relationship-only evidence does not assign function names, source
identity, compiler or exception semantics, ABI, arguments, register meaning,
purpose, runtime reachability, invocation, ordering, frequency, behavior,
effects, success, failure, termination, normal return, or Lua-side meaning.
This closes the exact layout join from the fourth callee to the already sealed
adjacent cluster beginning at `0x00378b3e`.

## Dependent residual direct-target-set static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary.json`
has analysis kind
`pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_static_boundary`.
It canonical-pins the pointer-target and adjacent-cluster artifacts, then
retains all eleven unique direct edges from `0x003729b0` as an exact partition:
five residual parents, five adjacent-cluster parents, and one deferred
`0x00372a53 -> 0x0039d580` parent. The adjacent rows exactly rejoin the cluster
artifact, while all five residual rows independently cross-join the exhaustive
target-reference scan.

The residual set contains three noncontiguous atlas bodies. Target
`0x00372970` is 50 bytes with all 21 instructions and a custom 21-node /
21-edge body-local CFG. Conditional `JE` at `0x00372980` retains both local
successors; the `E8` at `0x0037298a` retains fallthrough; final `E9` at
`0x0037299d` has no body-local successor and exactly rejoins the separate
out-of-body transfer to `0x003574ca`. Target `0x00007e70` is the one-byte
`RET` with a 1-node / 0-edge terminal CFG. Target `0x003581b3` is one six-byte
`FF 25` instruction and is represented as a 1-node / 0-edge opaque indirect
jump, not as a terminal return.

The complete declared outgoing-edge partition contains only the `E8` and
`E9` from `0x00372970`, both to `0x003574ca`. The complete indirect-control
partition contains only `FF 25` at `0x003581b3`. Its absolute-memory pointer
location is VA `0x007d6580` / RVA `0x003d6580` in file-backed non-writable
`.rdata`; the dynamic target remains unknown. Together with `JE`, `E8`, and
external `E9`, the complete PE-address audit contains three immediate `.text`
operands and one absolute-memory `.rdata` operand. All eight `call r32`
encodings are audited and absent. Direct Lua records are absent from the
pinned census, while staged Lua absence is bounded to the lack of local
call-r32 syntax and does not classify a dynamic target.

The full atlas scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly 736 target references survive: 719
five-byte `E8` calls and 17 five-byte `E9` other-address uses. Target counts
are `3/252/481` in body order and owner counts are `1/246/316`; the global
partition has 560 owners and the target-owner partition has 563 groups. No
absolute-memory target reference survives. The three independently pinned
partition SHA-256 values are `7208e20dcdff5e939aef709c668036da819b44bd609ee34b5bbfe09109492587`,
`cf1feca3f9046f1e0f2f06230bc009518f70b2f3926981fbcdf5e7848416bdac`,
and `e66aafd7e8153496d8f89842adb8ee37412180600ff09edd908f341a2a7187f8`
for the global-owner, target-owner, and target-reference projections.

The artifact's pretty-printed file SHA-256 is
`13784d112c47e9de5b0a92f7cfaac17245a98afb48214699ed516360b6d4d702`;
its canonical JSON SHA-256 is
`0783fffcd973eca3937ce01faa4d4f93b974540cfdaf004a301ce7ef0198fd5d`.
Publication uses the same immutable locked writer as the adjacent receipt,
including destination restriction, existing-content preservation, writer
contention, and failed-private-publication cleanup. Relationship membership,
analysis labels, decoded controls, and address syntax do not prove semantic
kinship, ABI, purpose, input/output meaning, runtime reachability, execution
order, termination, dynamic target identity, state mutation, success, effect,
data consumers, un-atlased code, or Lua-side behavior.

## Dependent deferred multi-range static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_multirange_static_boundary.json`
has analysis kind
`pe_native_query_handler_first_callee_pointer_target_multirange_static_boundary`.
It canonical-pins both the pointer-target and residual-target-set artifacts,
then exactly rejoins the residual artifact's sole deferred parent
`0x00372a53 -> 0x0039d580`. The target grouping is relationship-defined; the
analysis label attached to its atlas record remains metadata only.

The target contains two declared ranges. Range `0x0039d580` is 137 bytes with
46 instructions; range `0x0039d61f` is 27 bytes with 11 instructions. Their
joined 164-byte body has SHA-256
`1f4270f944215528deb2ae971345d562d784bd50acc000041cce365911b5ea67`.
The union CFG has 57 nodes / 57 edges and canonical SHA-256
`9f88252951d61c605a8deea0eb6e3e9cf1e85453e1515aded9c62b5539214d94`.
Only conditionals at `0x0039d5c9` and `0x0039d5e3` cross from the first range
to `0x0039d61f`; their first-range fallthroughs are also preserved. The
`RET` nodes at `0x0039d608` and `0x0039d639` are terminal, and no artificial
fallthrough crosses the undeclared gap.

The body has exactly two declared outgoing direct calls:
`0x0039d5bf -> 0x0039d640` and `0x0039d5d9 -> 0x0039d530`. Both remain opaque.
There is no indirect control or `call r32` syntax. The pinned direct-call census
contains no direct Lua call for the body, and locally evidenced staged Lua
dispatch is empty without classifying dynamic behavior.

The complete PE-address operand partition contains six immediates and one
absolute-memory read. The latter is operand index 1 at `0x0039d59c`, naming VA
`0x00893f28` / RVA `0x00493f28` in file-backed writable `.data`. The four
segment-qualified sites `0x0039d58f`, `0x0039d5aa`, `0x0039d5fa`, and
`0x0039d62b` are retained separately as exact `FS:[0]` syntax; the first is a
read at operand index 1 and the other three are writes at operand index 0. None
is misclassified as a PE absolute-memory operand.

The whole-atlas scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions. Exactly one entry reference survives: the parent
`E8` from sole owner `0x003729b0`. Other-address and absolute-memory reference
classes are empty. Owner, target-owner, and target-reference partition hashes
are `48a52d8519a9fcf7342f56530716af793f15fc620eddf0b856c0f303f37b93b6`,
`99510bf1ab711cd75f2eae4ec0f11de440eeb945b4d792956e64debdff48a1b2`,
and `82cbfb9dd0e25c2b8393c971ab66eb3c4de7b419718b89c1036ae18a164698c9`.

The artifact's pretty-printed file SHA-256 is
`ecf806bea49d116e0dd785d5d22aab4a769b51634efd1545acefa303d5c17778`;
its canonical JSON SHA-256 is
`a19a16ff5b999872acba98381163dc7d67113864ff508454d63162aa719e1c4e`.
Publication uses the immutable locked writer with destination restriction,
existing-content preservation, contention defense, and failed-private-output
cleanup. Relationship membership, analysis labels, decoded controls, PE
addresses, and `FS:[0]` syntax do not prove purpose, ABI, exception behavior,
runtime reachability, execution order, state mutation, success, normal return,
data contents, un-atlased references, or Lua-side behavior.

## Dependent multi-range direct-callee pair static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary.json`
has analysis kind
`pe_native_query_handler_first_callee_pointer_target_multirange_direct_callee_pair_static_boundary`.
It canonical-pins the multi-range artifact and exactly rejoins both outgoing
parents: `0x0039d5bf -> 0x0039d640` and
`0x0039d5d9 -> 0x0039d530`, from sole owner `0x0039d580`.

Target `0x0039d530` is a complete 67-byte / 33-instruction body with a
33-node / 36-edge body-local CFG. Target `0x0039d640` is a complete 49-byte /
19-instruction body with a 19-node / 19-edge CFG. Their graph canonical
SHA-256 values are
`f189c9abc78a31c21e1b5e479382105374ab05508d05b181cedd61083d3999cb`
and `94c13ceee9fdf0c3d9feeb6664abca7380f97df101a86dcc5265e12461bee80e`;
each body record exactly rejoins the graph object it names.

The complete PE-address partition is six immediate local branch targets in
file-backed nonwritable `.text`. Neither target has a declared outgoing direct
edge, opaque indirect control, `call r32`, segment-qualified memory operand,
direct Lua call, or locally evidenced staged Lua dispatch. The exhaustive
atlas scan covers all 25,312 functions, 25,490 ranges, 3,735,718 bytes, and
1,153,814 instructions across immediate and pure absolute-memory operand
classes. Exactly the two parent `E8` calls survive; no other-address or memory
reference does. Owner, target-owner, and target-reference partition hashes are
`751468fb4a47b8885547c9880c5a755f2b225f6c2f8253acc56f8231830bb5d6`,
`73f08fc635b2768f2e4fad7baf1861126489488faf00af74b8ef36d9c86a3ce0`,
and `4bc97f58b81bf1a9d3f70d3054f3df61718b7bed2d090b3cd63ac71f97716339`.

The artifact's pretty-printed file SHA-256 is
`bffdbec3554c1969563d4ac235a2e7d150aff311b5b277a31a9f413a3b5094e2`;
its canonical JSON SHA-256 is
`c479ae8d802d848877f8fd57475d8909e0fe2129d25182996d16f599b6cbaf8c`.
Publication uses the immutable locked writer. Parent relationship, decoded
layout, control flow, and PE syntax do not prove semantic kinship, purpose,
ABI, runtime reachability, execution order, success, normal return, state or
data meaning, un-atlased references, or Lua-side behavior.

## Dependent residual-target-set callee static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary.json`
has analysis kind
`pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_static_boundary`.
It canonical-pins the residual set and exactly rejoins its two transfers to
`0x003574ca`: `E8` at `0x0037298a` and `E9` at `0x0037299d`, both from owner
`0x00372970`.

The target is a complete 17-byte / four-instruction body with body SHA-256
`5eafe60e37cdb82b85f6df218e4b490940c6fb2545895c2cef644fb38ab97375`
and atlas-record SHA-256
`931454ae86cb6a227c6182c1abea3b232ee77a68a443b5a98f358f2418ff44b0`.
Its 4-node / 3-edge CFG has canonical SHA-256
`96b4b9365583495d1aa25d002d4833a064caf3792125584a8a6916bda9eb1a9d`.
The graph retains an `F2`-prefixed conditional, terminal return, and external
jump `0x003574d5 -> 0x00357b6a`. Prefix semantics and target behavior remain
opaque.

The complete PE-address partition contains one absolute-memory read in
file-backed writable `.data` plus two immediates in file-backed nonwritable
`.text`. Indirect controls, `call r32`, segment-qualified memory, direct Lua,
and staged Lua partitions are empty. The whole-atlas scan covers 25,312
functions, 25,490 ranges, 3,735,718 bytes, and 1,153,814 instructions. It finds
exactly 1,794 references from 1,620 owners: 1,790 standard `E8` calls, three
`F2 E8` calls, and one `E9` address use. Owner, target-owner, and
target-reference partition hashes are
`2496424b11c54f2dc558861a9469e4364f470a1b373cb93ed0b00eb4944790de`,
`e581d35f505204c2623a22d21e63fa5852d323a9e59ac2248ad6b681a178bfbb`,
and `64e5b02dda9ed08d40341ce46043a78eb705724bdf057ad885d59ef36feb993e`.

The artifact's pretty-printed file SHA-256 is
`548580d0fee7d612fe16bfe10b567ffd2c8d9a6add9cfd965a75c48c22123c2b`;
its canonical JSON SHA-256 is
`8e8a4c0d5c462bf20417b529313e634a76030214c34c35f0875e506a4f57f8b1`.
Publication uses the immutable locked writer. Relationship membership,
analysis labels, BND-prefixed syntax, decoded controls, and PE addresses do
not prove security purpose, source identity, ABI, runtime reachability,
execution order, termination, state mutation, success, data contents,
un-atlased references, or Lua-side behavior.

## Residual-target-set callee external-target static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary.json`
has analysis kind
`pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_static_boundary`.
It canonically pins the relationship-only external target `0x00357b6a`,
rejoins the exact `F2 E9` parent at `0x003574d5` from `0x003574ca`, and seals a
complete 251-byte / 56-instruction body with body SHA-256
`0a7f470e5151d95873547c1201fe9ad8d4c502d6afc9b530de59d9390eb9c0ed` and
atlas-record SHA-256
`324c7636ddd286b956053bb39fa045719f388d5254e441ce98b33d77d11fb074`.

Its enriched CFG has 56 nodes / 55 edges and canonical SHA-256
`020e22523160d01f527e80e62320f1052dc8654755d8aee3b8a88ae4dcc14048`.
`CD 29` at `0x00357b81` is retained solely as static terminal opaque interrupt
syntax, not a claim of runtime interrupt or termination behavior. Two opaque
direct calls remain: `E8 18 50 04 00` at `0x00357b75 -> 0x0039cb92` (SHA-256
`53a83b7d8c828fb30d1db99cb34f3ef39a9efff5068be6a8a626d05b2323b8df`) and
`E8 E1 FE FF FF` at `0x00357c5c -> 0x00357b42` (SHA-256
`d26d2f0423b8246000842d5f509221ff9bd0a727fd2fdbe6dfd975e060afd344`).

The complete PE-address partition contains four immediates and 24 writable
`.data` pure absolute-memory operands: 21 writes and three reads. Exactly six
are file-backed and 22 are explicitly virtual-only. `call r32`, indirect
controls, BND-prefixed controls, segment-qualified memory, direct Lua, and
staged Lua partitions are empty. The all-atlas scan covers 25,312 functions,
25,490 ranges, 3,735,718 bytes, and 1,153,814 instructions, finding exactly
one `other_address` reference from its sole owner `0x003574ca`.

The artifact's pretty-printed file SHA-256 is
`366bbfcf22cf6ed4dd667308336036191651c4d6dba3d48e6ae51271b66998c6`;
its canonical JSON SHA-256 is
`0d8bb3aecc53090dc5282844885ed327e79541ebaad4b7ca928e0494f86b08a9`.
## Residual-target-set callee external-target import-thunk static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary.json`
has analysis kind
`pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_import_thunk_static_boundary`.
It canonically pins relationship-only target `0x0039cb92`, rejoins its parent
`E8` at `0x00357b75`, and seals the complete one-instruction body:
`FF 25 10 60 7D 00`, six bytes, with body SHA-256
`247575b8ff280345c05bf6c58c3620b861c076bb718663401c6c729f4542cee7` and
atlas-record SHA-256
`495f4729075f0f38c369905e1cd00f3f3d9b1eb5247caf5ce112fec3e6066f4e`.

Its 1-node / 0-edge `indirect_jump` CFG has canonical SHA-256
`29e8bc268788c4dad137925a79b4350355d7f7db2dd2666bbc21399dd5bce60c`.
The instruction is not a return; runtime target, execution, and OS semantics
remain opaque. Its sole local PE operand is a file-backed, nonwritable
`.rdata` absolute-memory read of VA `0x007d6010` / RVA `0x003d6010`. Raw PE32
import metadata uniquely identifies `KERNEL32.dll!IsProcessorFeaturePresent`,
hint 772, no ordinal, as an import-table binding only. The receipt seals the
220-byte import directory (10 descriptors, 342 named imports, zero ordinal
imports, and 139 KERNEL32 rows); its exact descriptor, ILT, IAT, and hint/name
digests remain pinned in the artifact.

Outgoing direct calls, direct/staged Lua, `call r32`, BND-prefixed controls,
segment-qualified memory, and interrupt syntax are empty. The all-atlas target
frontier has exactly six `E8` calls from six owners; the independent IAT-slot
scan finds one absolute-memory indirect jump, this `FF 25` use. Both scans
cover 25,312 functions, 25,490 ranges, 3,735,718 bytes, and 1,153,814
instructions. Target scan partition SHA-256 values (owner, target-owner,
target-reference) are
`1bbecba81a7d7aa4aeca7f1f710d6f01f560569ffa80408e47615ced30e2abcd`,
`3a8c2764b1ef2d34109ba3afefbceac6055183a06bf28065f29b231f54dd0f8c`, and
`4ac37284ab3f41c7661c27432c2e89564f73e16913fa0f183b564f6d2330604e`.

The artifact's pretty-printed file SHA-256 is
`91397015cb9d8cd74fe2f18d648060c1e8cb28baa6b79f15f39e55ff77e3b71f`; its
canonical JSON SHA-256 is
`af117e253c45140863acc378051d6b5b1eba37458337aad43be6ef22d2589654`.
Its formerly retained sibling is sealed by the boundary below.

## Residual-target-set callee external-target second-callee static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary.json`
has analysis kind
`pe_native_query_handler_first_callee_pointer_target_residual_direct_target_set_callee_external_target_second_callee_static_boundary`.
It canonically pins relationship-only target `0x00357b42`, rejoins parent
`E8 E1 FE FF FF` at `0x00357c5c`, and seals the complete 40-byte / 12-
instruction body. Its body SHA-256 is
`5a4568c1047a793bff70d7632cc28b29500160dea29a7a4b913c8416835bee26`;
its atlas-record SHA-256 is
`c3417b9783a2a113a7f51883f10fd57557b7457ca184638a679cf15ac7ed863e`.
The enriched 12-node / 11-edge CFG has canonical SHA-256
`b3d334286def4ca119c59b70f91b17aa46c35b9737edf5088bf755b3f43e0b39`.

The body has four `FF 15` call-fallthrough syntaxes, each retained as opaque
indirect control plus a file-backed, nonwritable `.rdata` absolute-memory read:
slot RVA `0x003d60e4` at `0x00357b47`, `0x003d6018` at `0x00357b50`,
`0x003d60f0` at `0x00357b5b`, and `0x003d6014` at `0x00357b62`. Raw PE32
import metadata uniquely binds those slots to
`KERNEL32.dll!SetUnhandledExceptionFilter` (hint 1189),
`UnhandledExceptionFilter` (1235), `GetCurrentProcess` (448), and
`TerminateProcess` (1216), all named and non-ordinal. These bindings are
metadata only. The receipt revalidates the 220-byte import directory, its ten
descriptors, all 342 named / zero ordinal imports, 139 KERNEL32 rows, and each
slot's descriptor, ILT, IAT, hint/name, and library byte span and digest.

The all-atlas target frontier is exactly two immediate `E8` references from
two owners: `0x00357c5c` from `0x00357b6a` and `0x00357d38` from
`0x00357c71`. Owner, target-owner, and target-reference partition SHA-256
values are
`952f4d8d2d4027d45635f916a9f0160b633762f836754533bbb06ba29ae6ec3c`,
`ac04221eb3f1206725537a9fa5a263ad86b263e4d28dd8139f387fd294dc4614`,
and `0a36c89948e227a42750480cf04dbb59625da7d8d1437454a2e68ca4beade141`.
Four independent IAT-slot scans find respectively 3, 3, 5, and 13 references
for RVAs `0x003d6014`, `0x003d6018`, `0x003d60e4`, and `0x003d60f0`.
The final set contains 12 `FF 15` calls and the exact `8B 3D` absolute-memory
read at `0x00094fce`. All five closures check both immediate and pure
absolute-memory operands across 25,312 functions, 25,490 ranges, 3,735,718
bytes, and 1,153,814 instructions.

Outgoing direct calls, direct/staged Lua calls, `call r32`, BND-prefixed
controls, segment-qualified memory, and interrupt syntax are empty. The
artifact's pretty-printed file SHA-256 is
`5ccb1830fe36c58579b35089c68b84f0eb34bd5303eab72c09d4ed6b8b3096d2`;
its canonical JSON SHA-256 is
`f82310c91d26d3580458decdd70450c130f965ea53134cf0a383b7f9e5ea56d4`.
This branch's direct-target frontier is closed. The retained
`___raise_securityfailure` Ghidra analysis label, relationship membership,
import metadata, decoded syntax, and PE addresses do not prove semantic
identity, security, exception or termination behavior, purpose, source
identity, ABI, runtime reachability, imported-function execution, state
mutation, normal return, data meaning, un-atlased references, or Lua behavior.

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

## Dependent query-handler fourth-callee static-boundary artifact

`data/observatory/programs/windows_build_13725832_31fe35265598_native_query_handler_fourth_callee_static_boundary.json`
has analysis kind `pe_native_query_handler_fourth_callee_static_boundary`. It
canonical-pins the query-handler artifact and rejoins direct edge
`0x0038bc48 -> 0x003584f6` against the independently rebuilt entry-reference
row. The join pins exact instruction bytes, size, and SHA-256; source and
target atlas identities; immediate-`E8` form; and the normalized Ghidra edge.

The artifact seals the complete 21-byte target body, all 11 instruction
points, and its 11-node / 10-edge CFG. It has no direct native edge, direct or
staged Lua call, `call r32`, or retained literal. The whole-atlas scan covers
25,312 functions, 25,490 ranges, 3,735,718 bytes, and 1,153,814 instructions.
Exactly 67 target-entry references from 67 owners survive. Sixty-six are
five-byte immediate `E8` calls; the sole exception is the six-byte
BND-prefixed immediate jump at `0x0039d7c4`, owned by `0x0039d7b9` and
classified as an `other_address` use with no call form. Comparison and
absolute-memory entry-reference partitions are empty.

The instruction at `0x003584f9` has one exact `FS:[0]` destination-write
record. Its instruction bytes and SHA-256, operand index, segment,
displacement, absent base/index, and write access are pinned. The
segment-relative syntax is not represented as a PE absolute address and
carries no claim about the location's contents or behavior.

The artifact's pretty-printed file SHA-256 is
`2af1d59469ee8213ea8ae29bd0df46969af1b7c4acc9453f9d24ae06b655f9a7`;
its canonical JSON SHA-256 is
`d89c9a6eb25d63cd08830a0ee7beab1df5413aa6eb2b05ac791b8c1b7fedc05e`.
Publication validates one locked point-in-time snapshot, rejects writer
contention, normalizes inherited errors, preserves existing published
evidence after failed final validation, and removes a failed private
publication. The `__SEH_epilog4` analysis label does not prove purpose, SEH,
exception, epilog, stack, register, ABI, argument meaning, state mutation,
success, normal return, runtime reachability, source identity,
segment-relative contents, dynamic or computed references, data consumers,
un-atlased code, or Lua-side references.

## Explicit nonclaims

This survey does not prove that `class` is globally available at runtime, that
the string is a source-level class name, that allocation or initialization
succeeds, that setters/raw getters have the intended values, that the two
userdata objects have any particular native type or relationship, that registry
references remain valid, that helper calls return normally, or that the chain
covers indirect/dynamic/Lua-level consumers and mutations.
