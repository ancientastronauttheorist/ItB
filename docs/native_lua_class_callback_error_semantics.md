# Conditional callback argument-marker rejection

`src/observatory/native_lua_class_callback_error_semantics.py` is a standalone
pure Python model of the returned callback's argument-marker rejection. Its
endpoint is entry to the lua_error import at the call site RVA `0x002ec195`.
No DLL instruction, exception handler, unwind, assertion, or native callback
instruction executes here. The terminal import receives no modeled response;
the model makes no normal-return or nonreturn claim about that import.

The interface is
`apply(*, state, userdata, upvalue_kind, argument_has_metatable, argument_kind)`.
State and userdata must be exact nonzero uint32 ints, excluding bools and int
subclasses. The upvalue kind must be exact string `zero`, `empty_string`, or
`table`, all Lua-truthy. Argument metatable presence is an exact bool. With a
metatable, the argument marker kind is exact `nil` or `false`; without one it
must be `nil`. Other callback assertion and success families are excluded.

The initial Lua stack is one argument identity. The closure's upvalue is
preserved as userdata identity. First, direct touserdata at index -10003
supplies userdata. The marker helper's upvalue request then has a metatable:
getmetatable at -10003 pushes that table; pushstring adds the literal at VA
`0x0083c738`, `__luabind_classrep`; gettable at -2 replaces its key with a
supplied truthy marker; toboolean at -1 returns 1; settop(-3) restores the
original argument prefix. The lookup is metamethod-capable, not raw.

The argument marker request uses index 1. An absent metatable returns 0 and
adds nothing to the Lua stack. A present metatable repeats the lookup with nil
or false, toboolean returns 0, and settop(-3) restores the argument prefix.
The parent then pushes the message literal at VA `0x0083c99c`,
`expected class to derive from or a newline`, and reaches lua_error entry.

`calls` holds nine records for no argument metatable, or 13 for a present false
marker. Each carries full logical signed arguments, supplied API result,
before/after identity tokens, phase, and optional literal role. Phases are
`direct`, `upvalue_marker`, `argument_marker`, and `error`. Void results are
zero comparison placeholders. Lua_error's result is `None`, and its identical
snapshots describe an unexecuted import-entry boundary, not a VM stack effect.

`marker_results` records only the helper AL outcomes 1 and 0. The native helper
can retain supplied high 24 EAX bits on metatable paths after settop; this
logical model neither predicts nor infers those bits. Parent guards inspect AL.
`native_marker_requests` identifies the two index requests without executing
the native helper. `userdata` and `closure_upvalue` remain preserved output
identities. `error_entry_lua_stack` is argument plus message, with stack delta 1.

For callback entry ESP S, let EBP `F=S-4` and idle ESP `F-36`. The prior message
pushstring entry is `F-48`, containing native words
`[0x006ec194, state, 0x0083c99c]`. Its normal return leaves both arguments on
the stack. Error entry is `F-52`, with words
`[0x006ec19b, state, state, 0x0083c99c]`. The saved return-address word is
machine call syntax, not a claim that lua_error returns. The parent callback
sets up a cookie but has no FS registration or epilogue before this endpoint.

Tests independently apply Lua truth and stack operations for all three truthy
upvalue kinds crossed with the three absent/false argument modes. They also
check signed indices, API order, prefix restoration, exact literal/frame words,
strict input kinds and pointers, boundary words, and detached outputs. These
are conditional model laws, not live VM, import, unwind, source-class,
ownership, assertion-family, or successful-callback proofs.
