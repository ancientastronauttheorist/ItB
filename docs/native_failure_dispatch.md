# Conditional failure dispatch

The mismatch continuation at RVA `0x00357b6a` now has an independent
conditional specification through its feature-query branch. Its two stops are
exclusive: before the interrupt at `0x00357b81`, or before the fallback at
`0x00357b83`. Neither stop instruction nor any imported implementation runs
in this proof.

## Frame and query contract

Let F be the preceding owner's established frame. Entry ESP is F-812; the
new frame G is F-816. The prologue reserves 804 bytes, passes the value 23,
and calls the one-instruction import thunk at `0x0039cb92`. Its tail jump
adds no return word. Fresh PE import-table validation binds the thunk's
slot `0x003d6010` to `IsProcessorFeaturePresent`.

Microsoft documents feature value 23 as `PF_FASTFAIL_AVAILABLE` in
[IsProcessorFeaturePresent](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-isprocessorfeaturepresent).
This identifies the queried feature; it does not establish a live result.

The abstract query assumes a normal stdcall return with four argument bytes
removed, preserved nonvolatile registers, and preservation of the saved frame
and inherited return words at [G,G+8). All other memory is unspecified,
including newly reserved locals, outgoing scratch, earlier records and globals.
The return restores ESP to G-804, or F-1620. Volatile outputs remain opaque.

## Conditional result

For every unsigned 32-bit query return, zero reaches the fallback boundary;
nonzero reaches the interrupt boundary with ECX set to 2. EAX retains the query
return. ESP is G-804 in either case. The test establishes the reported zero
flag, but does not justify a universal complete flags image for future PUSHFD.

The static prefix contains 25 bytes and ten instructions, including the
unexecuted interrupt witness. The model covers nine prefix instructions and
the import thunk, with path-dependent visitation. Its 96 finite cases use
16 inherited frame alignments, three query results and two volatile-output
assignments: 64 stop before the interrupt and 32 before the fallback. These
are integer-model cases, not native or emulator executions.

## Evidence and reproduction

Artifact: `windows_build_13725832_31fe35265598_native_assertion_helper_failure_dispatch.json`.
Canonical SHA-256:
`9cddbfb1e39e64523390c31bac7bdaa12b6906593495235527d406db465e4e13`.
Raw UTF-8/LF SHA-256:
`531e1a6f00b39a3c80b12cdada984c847ecc134611927a238b06d2c36bdf2525`.

`scripts/itb_native_assertion_helper_failure_dispatch.py verify` takes
`--executable`, `--evidence`, `--owner`, `--frontier`, `--pair` and
`--program-facts`. It freshly decodes the prefix and thunk, validates their
pinned structural sources and import binding, and reconstructs the model.
`verify-structure` omits the executable; `build` omits the evidence and emits
deterministic JSON to standard output.

Independent tests cover branch classes, frame arithmetic, tail-thunk cleanup,
exclusive stops and receipt mutations. The exact executable rebuild passes.
Interrupt behavior, fallback stores, imported implementations and ultimate
termination remain outside this receipt. No whole-program accounting level
or exclusion is promoted.
