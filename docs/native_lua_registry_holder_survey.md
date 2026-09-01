# Native Lua registry-holder survey

Status: promoted executable-rebuilt census. This note records the exact
constructor-to-local-release fragment normalized by
`pe_native_lua_registry_holder_local_use_release_census`; it does not recover a
C++ type or establish a complete resource lifetime.

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
- Registry-holder local-use/release census:
  `data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_registry_holder_local_use_release_census.json`,
  analysis kind `pe_native_lua_registry_holder_local_use_release_census`,
  pretty-file SHA-256
  `139ed2444ee9b8824a4913638214db8c68a7899340a5e53b955c4a367c576755`,
  canonical JSON SHA-256
  `395603c2a163925fc202a5a35791200859313872c242fe5901e4de8c05ab892f`.

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

A complete exact-PE decode of every immediate and absolute-memory operand in
every function range declared by the program-facts atlas finds exactly 46
references to `0x00057970`. Every reference is an immediate five-byte `E8`
call, joins the matching Ghidra-declared direct edge, and comes from one of the
46 reviewed callers. Every source has a 247-byte atlas body. The call partition
has two address clusters:

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
The promoted artifact proves each `lua_rawgeti`, `lua_settop`, and `luaL_unref`
ESI stage dominates its accepted indirect calls, retains the complete CFG path
set, rejects every post-stage ESI writer on those paths, and makes its
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
The raw-lookup state is loaded through a separate temporary whose pointer is
first saved at `[esp+0x10]`; after intervening pushes, `E + 0x76` reloads that
temporary with `mov ebx,[esp+0x1c]`, then `E + 0x7f` pushes its `+0` field.
Exact equality between that state and the holder's state is not established.
The earlier `lua_rawgeti` at `E + 0x5e` is likewise not a proved use of the
constructor output.

By contrast, the release fragment reads the local state/ref pair at
`[esp+0x14]` and `[esp+0x18]`, checks the two guards, and only then calls
`luaL_unref(L, LUA_REGISTRYINDEX, ref)`. This establishes an exact conditional
local release attempt. It does not establish that the unref call executes,
succeeds, invalidates the reference, clears the native fields, or is the sole
release path. Each caller has a second later `luaL_unref` for a distinct stack
pair; it must not be attributed to the constructor output without an
independent provenance proof.

## Promoted fail-closed artifact

Build and verify the normalized artifact with:

```powershell
python -X utf8 scripts/itb_native_lua_registry_holder_local_use_release.py build `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --terminal-dispositions data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_terminal_dispositions.json `
  --output data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_registry_holder_local_use_release_census.json

python -X utf8 scripts/itb_native_lua_registry_holder_local_use_release.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --direct-calls data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_direct_call_census.json `
  --terminal-dispositions data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_cclosure_terminal_dispositions.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_registry_holder_local_use_release_census.json
```

The artifact seals 47 source bodies / 11,469 bytes and their 4,177 CFG nodes /
4,360 edges. The 46 callers contribute 11,362 bytes, 4,140 CFG nodes, 4,324
CFG edges, 92 direct Lua calls, 276 register-indirect calls, 1,702 semantic
instruction points, and 46 bounded EBX holder-use windows. The producer adds
its complete 33-instruction terminal sequence and all six direct Lua calls.
The whole-atlas scan covers 25,312 functions, 25,490 ranges, 3,735,718 bytes,
and 1,153,814 instructions; its only references to the producer are the 46
declared immediate `E8` calls.

Structural validation reconstructs every nested artifact field from the three
canonical-pinned prerequisites plus the sealed body, CFG, path, and instruction
profile. Exact validation independently decodes the PE, checks all operand
references, rebuilds every CFG, replays the terminal sequence, classifies every
`call r32` encoding, and recomputes each stage path and bounded EBX register-use
partition. Unknown fields and altered nested facts fail closed. Existing
byte-identical output is reused; symlink, reparse-point, non-regular, differing,
unrelated, or concurrently changed output is preserved and rejected.

## Explicit nonclaims

This survey does not prove runtime reachability, call success, call frequency,
state equality at the raw lookup, Lua reference validity, resource ownership,
native type identity, object lifetime, destruction completeness, persistence,
field clearing, absence of later uses, absence of indirect callers, or coverage
beyond the declared direct-atlas partition.
