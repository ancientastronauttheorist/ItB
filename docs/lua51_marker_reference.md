# Lua 5.1.5 marker reference experiment

An independently compiled 32-bit Lua 5.1.5 reference runtime now checks the
API sequence used by the native marker specification. This runs official
upstream Lua source with an authored C experiment. It loads no game DLL and
executes no native game helper.

The source archive is the 221,213-byte `lua-5.1.5.tar.gz`, SHA-256
`2640fc56a795f29d28ef15e13c34a47e223960b0240e8cb0a82d9b0738695333`,
published in the [official Lua download archive](https://www.lua.org/ftp/).
The producer requires that exact archive, extracts only its C/header source
members into private scratch, and verifies their hashes after compilation.
MSVC 14.29.30133 builds x86 code against SDK 10.0.19041.0. Compiler identities,
compiled source names, actual included-header hashes and experiment-source
hash are recorded. Raw source, compiler output and generated binaries remain
private.

## Tested behavior

The 70 cases combine five lookup setups, seven values and two valid index
forms. Each starts with three Lua stack entries: a number, subject table and
string. The subject is selected by index 2 or -2.

The setups are no metatable, direct marker lookup, table-valued `__index`,
function-valued `__index`, and an `__index` function that raises an error.
For metamethod cases, the subject's metatable T receives its own metatable M;
M supplies `__index`. Setting T's `__index` alone would exercise a different
lookup than the helper performs.

Values are nil, false, true, zero, empty string, table and function. The 56
normal cases restore all three entry stack slots and return the expected
truth value. Zero and empty strings are true. The 14 error cases are caught
by `lua_pcall`; their helper cleanup is not reached and is not claimed.
There are 28 calls to the authored function/error metamethods across the
matrix. Stack-prefix preservation does not imply unchanged table contents or
globals under arbitrary metamethods.

The expected results are authored separately from the C experiment and
compared record by record. The experiment supports the conditional Lua stack
contract in `docs/native_lua_class_marker_semantics.md`. It does not prove
that the installed game's Lua DLL is identical to this upstream build, nor
does it check native EAX upper bits or reproduce game instruction execution.

## Receipt and reproduction

Artifact: `data/observatory/programs/lua_5_1_5_x86_marker_reference.json`.
Canonical SHA-256:
`e6212ef1dc1f91861a894dfafca844607c8e4a2aecf9e95dd4fea8c565ef9a34`.
Raw SHA-256:
`56a5956cf5f69e6f74f962681b53969775c2b5615da6b301cfece85f35285f08`.

`scripts/itb_lua51_marker_reference.py verify --archive <official-archive>
--evidence <receipt>` rebuilds the experiment using the fixed local toolchain.
`verify-structure` needs only `--evidence`. `build --archive <official-archive>`
emits deterministic UTF-8 JSON. The tool does not download sources itself.

Independent tests verify truth/error partitions, parser rejection of changed
results, receipt mutations and byte-identical output from a fresh source
compile. This receipt makes no whole-game accounting promotion.
