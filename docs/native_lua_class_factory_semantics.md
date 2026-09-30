# Conditional complete factory request model

`src/observatory/native_lua_class_factory_semantics.py` composes the independent
factory-prefix model with the normal initializer Lua requests and factory tail.
It describes a complete normal return under supplied Lua/context responses.
It does not execute native instructions, allocation code, a Lua VM, registry
operations, metamethods, assertions, or exception handlers.

The interface is
`apply(*, state, first_pointer, second_pointer, userdata, name_bytes,
context_pointer, context_word, context_guard, metatable_reference,
graph_pointer, id_map_pointer, references)`.

Pointers and the state word are exact nonzero uint32 ints. Context word/guard
are exact uint32 ints; guard `0xfffffffe` is excluded because it selects an
assertion arm. The metatable reference is an exact nonnegative signed-32 int.
`references` is an exact list of three distinct positive signed-32 luaL_ref
response words, keeping the fresh table1/table2/userdata identities independent.
These are ordered supplied response/binding requests, not a reconstructed
registry. The full userdata write extent through byte 71 and context read
extent through byte 19 must not wrap. Graph/id-map words remain opaque pointers.

`name_bytes` and the first pointer use the prefix model's first-NUL and cursor
checks. The supplied objlen response equals the measured first-NUL offset;
synthetic trailing bytes are ignored. The second tolstring pointer remains
independent: its bytes are never inspected, so no claim says its handed-off
name is the measured or validated byte sequence.

`calls` contains 34 ordered records with API name, full logical signed argument
words, supplied result, before/after Lua stack snapshots, phase, and optional
literal role. The partition is seven factory-prefix calls, 23 initializer
calls, then four factory-tail calls. Void API results use zero as a comparison
placeholder. The normal lua_setmetatable result is 1; luaL_ref results and
pointer conversions carry the supplied words. The first seven results are the
existing prefix contracts: 1, 4, 0, first pointer, measured length, second
pointer, and userdata.

The initializer creates two independent table identities. Each is duplicated
and its duplicate consumed by luaL_ref. `lua_settop(-3)` removes the retained
two tables, restoring argument/userdata. Three registry lookups use these
literal pointer roles:

| Role | Literal | Pointer |
| --- | --- | --- |
| classes | `__luabind_classes` | `0x0083bf18` |
| cast_graph | `__luabind_cast_graph` | `0x0083bf6c` |
| class_id_map | `__luabind_class_id_map` | `0x0082a86c` |

Each uses pushstring, metamethod-capable gettable at index -10000, touserdata,
and settop(-2). Between the first and second lookups, rawgeti requests the
supplied metatable reference, setmetatable consumes that value for userdata,
and duplicate-userdata luaL_ref obtains the third reference. Every context
lookup is a supplied compatible value; the model does not infer validity from
its key or pointer.

`registry_bindings` records first-reference/table1, second-reference/table2,
and third-reference/userdata contracts. `metatable_setting_request` describes
the userdata/reference request. The tail pushes the opaque second name,
duplicates userdata, and requests global settable at -10002. It then consumes
userdata as the single upvalue of a closure targeting VA `0x006ec110` / RVA
`0x002ec110`. `global_assignment_request` records the name pointer and userdata;
it does not claim raw storage or absence of metamethod effects.

`final_lua_stack` retains the original argument followed by the closure.
`result_count=1` and `selected_results` select that closure. The stack values
are identity tokens, not live VM values. Mutable output containers are detached
from inputs, adjacent snapshots, and repeated model calls.

`final_fields` gives only offset-level native final words: literal at 0; zeros
at 4/8/12; second name pointer at 16; state/third-reference at 20/24;
state/first-reference at 28/32; state/second-reference at 36/40; 1 at 44;
context word at 48; zeros at 56/60; graph pointer at 64; id-map pointer at 68.
Offset 52 holds the native helper's allocation return and is deliberately
omitted, listed in `unmodeled_fields`. The native allocator and its record
stores are outside this model. `context_reads` records supplied +12/+16/+8
values without naming a source-level representation, ownership, or lifetime.

Tests independently interpret every API stack effect and verify exact argument
order, supplied results, phase boundaries, literal roles, bindings, final
fields, first/second pointer independence, bounded byte/reference/context
families, strict type rejection, assertion exclusion, extent checks, and
output detachment. These are model laws, not executable conformance or a proof
that a live global class factory exists or succeeds.
