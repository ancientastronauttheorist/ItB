# Lua 5.1.5 filtered-assignment reference experiment

A separate official Lua 5.1.5 build now checks 48 concrete filtered-assignment
API experiments: 42 normal returns and six protected errors. It exercises
the API contract in `docs/native_lua_filtered_assignment_semantics.md` without
loading the game's Lua DLL or executing native game instructions.

## Cases and observations

Four destination setups cover a direct table, a table whose `__newindex`
redirects to another table, userdata with an assignment callback, and userdata
with an error-raising callback. Six source patterns range from empty and
reserved-only tables to a mixed table. Two stack-prefix lengths check suffix
handling without changing the destination/source positions.

The mixed source contains both reserved string keys and six unfiltered keys:
an ordinary string, zero, empty string, userdata with an equality handler,
false, and `__init` followed by a NUL and additional bytes. The independent
result oracle checks exact string type and byte length. It verifies that only
the two exact reserved strings are skipped and that no userdata equality
handler is invoked by the filter.

Normal cases verify restored entry stack slots and exact values in the
actual destination or redirected result table. Final table entry counts
detect extra writes. Validation does not assume `lua_next` order. The chosen
callbacks do not mutate the source; arbitrary callback mutation and eventual
exhaustion are not established. Error cases observe one assignment request,
one callback and an error caught by `lua_pcall`; helper cleanup is not reached
or claimed.

## Provenance and reproduction

The producer shares the fixed private source compiler with
`docs/lua51_marker_reference.md`: official Lua 5.1.5 archive SHA-256
`2640fc56a795f29d28ef15e13c34a47e223960b0240e8cb0a82d9b0738695333`,
MSVC 14.29.30133, SDK 10.0.19041.0, x86. All source/header identities and the
authored C experiment hash are recorded. The archive is available from
[Lua's official download archive](https://www.lua.org/ftp/).

Artifact: `data/observatory/programs/lua_5_1_5_x86_filtered_assignment_reference.json`.
Canonical SHA-256:
`7d82034b09049dd4eefa96cb02f004dfc15661e8572d4a2267ec4e0473185b35`.
Raw SHA-256:
`aa3a701d5b74f4e774727e21db0a4eeaa0953f935bf4fb9e4cd141ea80bb80ee`.

`scripts/itb_lua51_filtered_assignment_reference.py verify` takes `--archive`
and `--evidence`; `verify-structure` needs only evidence. `build --archive`
emits deterministic UTF-8 JSON. The tool performs no download itself.
Independent tests verify result partitions, changed-result rejection, receipt
integrity and byte-identical output from a fresh compile. The shared harness's
earlier marker receipt also rebuilds unchanged.

These are finite upstream reference results, not installed-DLL equivalence,
native register conformance or whole-game accounting.
