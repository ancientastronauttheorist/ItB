# Finite Lua helper reference contracts

This receipt links specific observations from the two upstream Lua 5.1.5
experiments to the abstract contracts of the native marker and filtered
assignment helpers. It compares 98 normal rows and explicitly excludes 20
protected errors from normal-return claims.

The 56 marker rows comprise 14 without a metatable, 12 with a false marker and
30 with a true marker. The compared observations are the Boolean result
against the native AL predicate, Lua stack delta and entry-prefix preservation.
Reference results do not establish native EAX upper bits or native stack and
register behavior.

The 42 normal assignment rows compare assignment-request counts, Lua stack
delta and entry-value preservation. They total 48 assignment requests. An
unordered key-class inventory supplies the permutation-invariant filter count;
the receipt neither reconstructs nor claims to observe `lua_next` order.
It does not compare native traces, API-call counts, full EAX or destination
heap effects. The six assignment errors and fourteen marker errors remain
outside these normal contracts.

All seven source identities are pinned and their existing native/reference
validators run before the comparisons. Three changed-observation controls must
fail. This tool performs no native execution, reference compilation or replay
of earlier matrices. The native and upstream-reference evidence domains remain
distinct, with installed-DLL equivalence and whole-game accounting unproved.

Artifact: `windows_build_13725832_31fe35265598_native_lua_helper_reference_contracts.json`.
Canonical SHA-256:
`a7c0b4544d1263bf6bcfcf9c2cae613eddd86b1367c1e9fb7d23d2075e545ebf`.
Raw SHA-256:
`f309f0703dd1598878d089e780e1c7a69b5fe7eb6d5379b695d5554c01bf36f1`.

`scripts/itb_native_lua_helper_reference_contracts.py build` takes
`--marker-native`, `--marker-reference`, `--assignment-native`,
`--assignment-reference`, `--chain`, `--direct-calls` and `--program-facts`.
It emits deterministic UTF-8 JSON. `verify-structure` takes the same sources
plus `--evidence`; neither command requires the game executable or compiler.

The component contracts and experiments are documented in
`docs/native_lua_class_marker_semantics.md`, `docs/lua51_marker_reference.md`,
`docs/native_lua_filtered_assignment_semantics.md` and
`docs/lua51_filtered_assignment_reference.md`.
