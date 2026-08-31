# Native Lua registry-holder survey

Status: read-only static research checkpoint. This note records one exact
constructor-to-local-release fragment for the Windows executable; it does not
recover a C++ type or establish a complete resource lifetime.

## Bound inputs

All claims are specific to the x86 Windows `Breach.exe` from build `13725832`,
SHA-256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.

The required, build-bound artifacts are:

- Program-facts atlas:
  `data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json`,
  analysis kind `pe_ghidra_program_facts`, canonical SHA-256
  `631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803`.
- Direct Lua import-call census:
  `data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json`,
  analysis kind `pe_native_lua_direct_import_call_census`, canonical SHA-256
  `07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608`.
- Terminal-disposition census:
  `data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_terminal_dispositions.json`,
  analysis kind `pe_native_lua_cclosure_terminal_disposition_census`, canonical
  SHA-256 `74b762e486611a6dc71325276d9e8e92b7894de30f99bacf9e301e894c85bb85`.
  Its `registry_reference_holder` record pins the constructor sequence below.

Addresses are image-relative RVAs. Lua API semantics use the Lua 5.1 ABI,
including `LUA_REGISTRYINDEX == -10000` and the no-reference sentinel `-2`.
Those are ABI premises rather than evidence that a particular execution
reaches, succeeds at, or retains any Lua operation.

## Constructor and field layout

The exact 107-byte atlas body at `0x00057970` has body SHA-256
`a2a4f2291ef2d6afb98599d9f713d9f2ebe3bace50aea021ba0b46a859e1f501`.
The existing terminal-disposition record proves this reviewed local sequence:

| role | RVA |
| --- | --- |
| first registry `lua_rawgeti` | `0x00057982` |
| second registry `lua_rawgeti` | `0x00057994` |
| two-upvalue native closure push | `0x000579a2` |
| store state from EDI at holder offset `+0` | `0x000579ab` |
| initialize holder offset `+4` to `-2` | `0x000579ad` |
| `luaL_ref(L, LUA_REGISTRYINDEX)` | `0x000579c0` |
| store returned reference at holder offset `+4` | `0x000579c9` |
| return the ECX-supplied holder address in EAX | `0x000579d5` |

The static field layout is consequently only:

```text
holder +0 : state value written from EDI
holder +4 : -2 initially, then the returned luaL_ref integer
```

It does not imply a native class name, ownership policy, valid registry
reference, or a destructible type outside the reviewed sequence.

## Complete declared direct-caller partition

A complete exact-PE decode of every function range declared by the
program-facts atlas finds exactly 46 direct calls targeting `0x00057970`.
Every source has a 247-byte atlas body. The call partition has two address
clusters:

| cluster | source entries | count | stride |
| --- | --- | --- | --- |
| low-RVA cluster | `0x00054740` through `0x000550d0` | 9 | `0x130`, except the one `0x140` gap from `0x00054e60` to `0x00054fa0` |
| high-RVA cluster | `0x0028f3f0` through `0x00291eb0` | 37 | `0x130` |

The 46 complete body hashes are intentionally retained by the atlas rather
than replaced by one claim of byte identity: each caller has a distinct body
hash because its PC-relative instructions and nearby target differ. Their
decoded holder fragment has one repeated relative-RVA grammar. The following
facts must therefore be read as a 46-record finite partition, not as a claim
that all native callers or indirect calls have been discovered.

## Repeated caller grammar

Let `E` be one of the 46 caller entry RVAs and `S` be the caller's stack
position immediately after the prior callee-cleaned setup call returns. The
following decoded sequence is common to all 46 bodies:

| relative RVA | exact role |
| --- | --- |
| `E + 0x25` | `lea ecx,[esp+0x14]`: select an 8-byte stack-local holder destination |
| `E + 0x2a` | direct `call 0x00057970` |
| `E + 0x2f` | remove the one pushed constructor argument |
| `E + 0x35` | `mov ebx,eax`: retain the returned holder pointer |
| `E + 0x45` | stage `lua_rawgeti` IAT address in ESI |
| `E + 0x73` | read the returned holder reference with `push dword ptr [ebx+4]` |
| `E + 0x81` | staged `lua_rawgeti` call using that reference |
| `E + 0xae` | load stack-local holder state from `[esp+0x14]` for release |
| `E + 0xb2` | stage `luaL_unref` IAT address in ESI |
| `E + 0xbc` | load stack-local holder reference from `[esp+0x18]` for release |
| `E + 0xb8` / `E + 0xc0` | guards for state nonzero and reference not equal to `-2` |
| `E + 0xcc` | conditional staged `luaL_unref` call |

For the first source entry, those are respectively `0x00054765`,
`0x0005476a`, `0x0005476f`, `0x00054775`, `0x00054785`,
`0x000547b3`, `0x000547c1`, `0x000547ee`, `0x000547f2`,
`0x000547fc`, `0x000547f8` / `0x00054800`, and `0x0005480c`.

The `lua_rawgeti` stage is the named Lua 5.1 import at IAT RVA `0x003d64c0`;
the `luaL_unref` stage is the named Lua 5.1 import at IAT RVA `0x003d64ec`.
A future exact artifact must prove each ESI stage dominates its indirect call,
reject every post-stage ESI writer on the accepted path, and make its
32-bit-Windows-cdecl nonvolatile-register premise explicit.

The decoded bodies contain no explicit post-return write through EBX to
`[ebx]` or `[ebx+4]`, no call receives the returned holder address itself, and
no explicit field copy to a persistent native destination appears. The `+4`
reference is separately passed to `lua_rawgeti` as documented below. Within
this bounded grammar, the constructor output stays in the caller's stack-local
slot. This is not a proof about changes an arbitrary callee may make or about
unmodeled/indirect paths.

## Raw lookup and conditional release boundary

The `E + 0x73` read proves that the constructor output's `+4` reference field
is supplied to the later registry `lua_rawgeti`. It does **not** prove that the
state argument to that raw lookup comes from the output holder's `+0` field.
The raw-lookup state is loaded through a separate temporary whose pointer was
saved at `[esp+0x10]`; exact equality between that state and the holder's state
is not established. The earlier `lua_rawgeti` at `E + 0x5e` is likewise not a
proved use of the constructor output.

By contrast, the release fragment reads the local state/ref pair at
`[esp+0x14]` and `[esp+0x18]`, checks the two guards, and only then calls
`luaL_unref(L, LUA_REGISTRYINDEX, ref)`. This establishes an exact conditional
local release attempt. It does not establish that the unref call executes,
succeeds, invalidates the reference, clears the native fields, or is the sole
release path. Each caller has a second later `luaL_unref` for a distinct stack
pair; it must not be attributed to the constructor output without an
independent provenance proof.

## Candidate fail-closed artifact

A narrow next artifact could be named
`pe_native_lua_registry_holder_local_use_release_census`. It should compose the
three bound prerequisites and retain one record per declared direct caller,
plus one exact producer record. It should publish only:

- atlas body identities, normalized RVAs, instruction sizes, and SHA-256
  instruction facts;
- the producer's exact two-field layout and return-register witness;
- the declared direct edge and caller-local destination grammar;
- the separately labeled ref-to-`lua_rawgeti` and state/ref-to-`luaL_unref`
  data-flow witnesses;
- complete CFG/entry audits, stage-to-call path sets, and guard edges; and
- deterministic cluster/count aggregates.

It must fail closed if the executable, atlas identity, terminal-disposition
identity, direct-import identity, caller partition, field offsets, local stack
offsets, import IAT stages, guard constants, or stored CFG facts differ.

Minimum adversarial tests should independently alter:

1. the producer body identity, field store, sentinel, or returned-register
   transfer;
2. a declared caller edge, call offset, local destination, or EBX transfer;
3. the ref-field read, rawgeti IAT stage, registry selector, or a post-stage
   ESI clobber;
4. the state/ref cleanup offsets, either guard, sentinel comparison, unref IAT
   stage, or cleanup branch edge;
5. a fabricated state-equality assertion, persistent-holder copy, or reset;
6. an alternate atlas entry into an accepted region, a missing caller, a
   duplicate caller, or a changed cluster aggregate; and
7. any prerequisite canonical digest or exact-PE instruction rebuild.

A PE-free structural validator may replay retained hashes, paths, dominance,
and aggregates. It cannot establish decoded instruction semantics, literal
bytes, register-write classification, or Lua import identity without the exact
bound executable rebuild.

## Explicit nonclaims

This survey does not prove runtime reachability, call success, call frequency,
state equality at the raw lookup, Lua reference validity, resource ownership,
native type identity, object lifetime, destruction completeness, persistence,
field clearing, absence of later uses, absence of indirect callers, or coverage
beyond the declared direct-atlas partition.
