# Conditional Lua class-marker predicate

The 84-byte helper at RVA `0x002eb560` now has an independent specification
covering all 32 instructions and its three normal-return paths. It accepts a
Lua state in ECX and an index in EDX, and checks the truth of the marker
`__luabind_classrep` in the selected value's metatable. A truthy marker does
not establish a native type or class identity.

## Lua and native stack behavior

With no metatable, the first API returns zero, the Lua stack remains unchanged
and the native result is zero. With a metatable, the helper pushes the marker
key, performs ordinary `lua_gettable` indexing at -2, tests the resulting value
at -1 with `lua_toboolean`, and removes the result and metatable with
`lua_settop(-3)`. All normal paths restore the entry Lua stack prefix.

Only nil and false are false; zero and empty strings are true. The lookup is
metamethod-capable, so heap and global side effects remain unconstrained.
Normal API returns, valid Lua state/index/capacity and the stated stack effects
are explicit premises. Errors and nonlocal exits are excluded from the normal
path proof. See the [Lua 5.1 API manual](https://www.lua.org/manual/5.1/manual.html#lua_gettable).

The x86 model checks cdecl argument handling separately. Each API receives
eight argument bytes; the callee removes only its return address. Three
retained argument pairs are discarded together by a 24-byte caller cleanup.
The final pair has its own eight-byte cleanup. Saved ESI and the incoming
return word are the only native memory words retained across abstract APIs.
ESI and the other nonvolatile registers are restored; final ESP is entry+4.

The return writes only AL. On a metatable path, full EAX is the last void
`lua_settop` call's opaque upper 24 bits with AL replaced by zero or one.
For example, a false result can leave EAX=`0xdeadbe00`. The known parent
consumers test AL, not the full register. The no-metatable path has full EAX
zero from `lua_getmetatable`.

## Evidence and limits

The 576 integer/abstract-stack cases cover all 32 instructions, six import
call sites, five API bindings and three path classes. Three mutated operation
controls execute and must fail semantic or memory checks. Exact PE grammar,
body and source joins pin the analysis to the accepted Windows executable.
No imported implementation or game instruction executes in this model.

The separate reference-runtime experiment in `docs/lua51_marker_reference.md`
checks 70 actual upstream Lua 5.1.5 API cases, including protected errors.
Its finite reference results are distinct from this native register model;
installed-DLL equivalence and whole-game conformance remain unproved.

Artifact: `windows_build_13725832_31fe35265598_native_lua_class_marker_semantics.json`.
Canonical SHA-256:
`fb30c2feb6bcbc4583ee415585405a130b1219952d23c9aecdf56103158a7c7d`.
Raw SHA-256:
`03efb733a13e11d102174abe2231c5a36f43df58f15d272a5ad32d2c19692540`.

`scripts/itb_native_lua_class_marker_semantics.py verify` takes
`--executable`, `--evidence`, `--chain`, `--direct-calls` and `--program-facts`.
`verify-structure` omits the executable; `build` omits evidence and emits
deterministic UTF-8 JSON. Independent tests verify partial-register results,
Lua truth classes, both stack contracts, mutations and an exact byte-identical
CLI rebuild. No accounting level or exclusion is promoted.
