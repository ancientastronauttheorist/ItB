# Compiled Lua 5.1 census

This directory is the publication boundary for build-keyed, metadata-only
analysis of the installed Lua and map corpus. Eligible artifacts contain file
identities, compiled prototype structure and hashes, source spans, opcode
counts, identifier-only environment/member accesses, callback joins, and
modeled loader edges. They must not contain Lua source text, literal payloads,
binary chunks, decompiler output, or absolute installation paths.

The current Windows artifact is
`windows_build_13725832_31fe35265598_lua51_census.json`. Its exact-install
verification covers:

- 529 compiled-but-never-executed chunks: 152 accepted script Lua files,
  `maps/maphelper.lua`, and 376 Lua-form `.map` chunks;
- 915 nested function prototypes plus 529 chunk roots, paired one-to-one with
  lexical function trees and exact source line ranges;
- 173,619 decoded Lua 5.1 instructions and 2,686 environment identifiers;
- all 757 definitions in the existing callback provenance index;
- 523 modeled load edges: 145 compiler/source-derived edges and 378 explicit
  host assumptions, covering 520 accepted files and leaving nine explicit
  `unrouted_in_static_load_model` files; and
- the local Mod Loader overlay and three backups as named exclusions rather
  than shipped-game Lua.

The artifact's pretty-printed file SHA-256 is
`0747383a8932129bdb001555d6e7975cd7b725995343ac269a678f052f2e154b`.
The verifier's canonical JSON SHA-256 is
`389578d2e85ae9b5563d0c158cbbd7c3d5a75ca0adcdca7a51116b0bc56b49e0`.

## Exact compiler helper

The build uses the inventoried 32-bit `lua5.1.dll` itself. On every build or
verification, the Python driver compiles `scripts/windows_lua51_dump.rs` into a
temporary x86 PE with the recorded Rust toolchain and deterministic `/Brepro`
linking, verifies the PE architecture, and invokes that exact fresh binary.
The helper calls `luaL_loadbuffer` and `lua_dump`; it never calls a Lua chunk,
and it enforces 64 MiB source and 512 MiB bytecode protocol limits.

The normalized artifact records the helper source, build arguments, Rust
compiler version/hash, reproducible helper binary hash/size/architecture, DLL
identity, and emitted chunk header. The helper executable and dumped chunks
are temporary and never enter Git. The `i686-pc-windows-msvc` Rust target must
be installed; `--rustc` can name a compiler outside `PATH`.

## Build

```powershell
$itbInstall = "<path-to-Into-the-Breach-install>"
python -X utf8 scripts/itb_lua_census.py build `
  --install-dir $itbInstall `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --callback-index data/observatory/callbacks/windows_build_13725832_31fe35265598_callback_index.json `
  --output data/observatory/lua/windows_build_13725832_31fe35265598_lua51_census.json
```

Repository output is restricted to a direct child of this directory and is
written atomically. An existing artifact of another kind is never replaced.

## Verify

```powershell
$itbInstall = "<path-to-Into-the-Breach-install>"
python -X utf8 scripts/itb_lua_census.py verify `
  --install-dir $itbInstall `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --callback-index data/observatory/callbacks/windows_build_13725832_31fe35265598_callback_index.json `
  --evidence data/observatory/lua/windows_build_13725832_31fe35265598_lua51_census.json
```

Verification rebuilds the entire installation inventory, recompiles every
accepted chunk with the exact DLL, reparses every prototype, repeats the
callback and load-graph joins, and requires exact normalized equality.

## Claim boundary

This is a complete static compiled-prototype and identifier census for the
accepted owner-build corpus, not a semantic decompile. `GETGLOBAL` and
`SETGLOBAL` operate on a function environment; two accepted-corpus sites use
`setfenv(1, ANIMS)`, so those accesses cannot all be called `_G` accesses.
Twenty-seven computed `_G[...]` sites, including four writes, do not expose
their runtime keys statically. `loadstring` can generate additional code.

The direct literal table returned by `GetScripts` and supported literal
`dofile` syntax sites are compiler/source-cross-checked facts, but do not prove
runtime reachability. The two host bootstraps and 376 map-directory discovery
edges are explicit assumptions pending native loader reconstruction.
Unresolved host environment/member names are candidates, not proof of C++
registration. The artifact does not claim runtime reachability, load order,
native-binding completeness, control-flow semantics, behavioral equivalence,
optional user or mod code, pristine-depot identity, or cross-build equality.
