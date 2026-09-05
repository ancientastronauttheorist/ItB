# Conditional filtered Lua assignments

The 180-byte helper at RVA `0x002ec050` now has an independent specification
covering all 71 instructions. It reads a Lua stack suffix containing destination
and source, traverses a supplied valid `lua_next` transcript, skips exact string
keys `__init` and `__finalize`, and requests assignments for all other keys.
Assignments use `lua_settable`, so they can invoke `__newindex` and need not be
raw writes to the destination object.

## Loop contract

Each successful `lua_next` establishes the suffix destination, source, key,
value. The two comparisons add one literal at a time. A matching reserved
key drops the value and literal while retaining the iterator key. Otherwise,
the helper duplicates the key and rearranges the suffix to destination,
source, iterator key, duplicate key, value. `lua_settable(-5)` consumes the
last key/value pair, leaving the iterator key for the next step.

Only exact strings match the two literal filters. Other key types do not
coerce to strings. Although Lua equality is generally capable of invoking
metamethods, these literal-string comparisons cannot invoke a key's `__eq`
handler. A string with additional bytes after an embedded NUL is not the
reserved string. The ordinary API rules are documented in the
[Lua 5.1 manual](https://www.lua.org/manual/5.1/manual.html#lua_equal).

Initialization and each of the three local paths establish a checked stack
invariant. Normal exhaustion removes the last iterator key and restores the
entry Lua stack. Full EAX is zero from the final `lua_next`; it is independent
of earlier void-call clobbers. Native ESP ends at entry+4 and nonvolatile
registers are restored. The nonempty path also checks its staged import
addresses in EBX and EDI and their conditional saved-word lifetimes.

A finite transcript with n keys causes assignment requests exactly at the
positions classified as other. API count is two plus four per `__init`, seven
per `__finalize` and ten per other key. This counts each iteration's next call.
It does not prescribe iteration order or prove that callbacks cannot mutate
the source. The supplied transcript must be valid and end in normal exhaustion;
errors, nonlocal exits and nontermination remain outside the normal proof.
Destination validity is an API premise, not a blanket requirement that it be
a table: valid `__newindex` behavior can handle other Lua objects.

## Evidence and reproduction

The 2,560 integer/abstract-stack cases combine all 40 key-class transcripts of
length zero through three, 16 native alignments, two Lua prefix lengths and
two void-call clobbers. They cover all 71 instructions, eight direct and six
staged import sites, and eight distinct APIs. Mutated operations must fail
downstream semantic or memory guards. No game code or imported implementation
executes in this model.

Artifact: `windows_build_13725832_31fe35265598_native_lua_filtered_assignment_semantics.json`.
Canonical SHA-256:
`b62b6409f2f3f3a003732bc106f5e4e3f0eaf543d2b246984a6513cc658a1b27`.
Raw SHA-256:
`b702b24ca55a586ac3be3acf0e8d357623d3431c707821d46647b2308779fc1b`.

`scripts/itb_native_lua_filtered_assignment_semantics.py verify` accepts
`--executable`, `--evidence`, `--chain`, `--direct-calls` and `--program-facts`.
`verify-structure` omits the executable; `build` omits evidence and emits
deterministic JSON. Independent tests check request positions, API counts,
stack induction, larger finite relations, invalid inputs and an exact CLI
rebuild. The separate reference experiment is documented in
`docs/lua51_filtered_assignment_reference.md`. No accounting level is promoted.
