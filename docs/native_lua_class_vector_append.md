# Conditional class-vector append

The interval `[0x002eb1bb,0x002eb21a)` now has an independent specification
for 95 bytes and 36 instruction sites. It begins after the enclosing helper's
tree loop and stops before its cookie epilogue. The object pointer comes from
[F-12]; its fields at offsets 4, 8 and 12 supply begin, end and capacity.
EDI supplies the input address and native ESP starts and ends at F-32.

## Alias and memory relation

The unsigned interval test classifies an argument A as internal exactly when
begin <= A < end. An internal argument is converted to a saved signed
arithmetic-shift index `(A-begin) >> 3`. After optional growth, the helper
rereads begin and computes the source from that saved index. External
arguments retain their original address. Growth is requested when the initial
end equals capacity.

The machine relation is explicit about alignment and 32-bit arithmetic.
For a coherent aligned eight-byte element, rebasing retains the intended
element. An unaligned internal address rounds down to a record boundary.
High-bit displacements use signed arithmetic shift, not unsigned division.
Pointer classification alone establishes neither object validity nor source
lifetime after growth.

If the post-growth destination end is nonzero, two DWORD reads and writes
interleave: read first word, write first word, read second word, write second
word. An overlapping destination can therefore change the second read.
This is not a snapshot copy. A zero destination skips both copies but still
increments the end field by eight, with machine-width wraparound.

The direct growth body has a separate 94-byte/40-instruction static witness.
Its implementation is not executed or inferred. The abstract growth contract
requires normal return, preserved frame/object identity and nonvolatile
registers, declared post-growth layout and mapped payloads. The pushed word
has no effect under that summary. Its RET-4 convention restores ESP from
callee-entry F-40 to F-32. Relocated element preservation and external source
readability are explicit premises where used.

## Integer model and exact replay

The semantic receipt checks 416 integer/ordered-memory cases across 13
profiles, 16 frame alignments and two data seeds. All 36 instruction sites
are represented, with 128 abstract growth calls. Cases include unaligned
inputs, overlap and null destinations; some are synthetic machine states and
are not claimed to be valid C++ vector objects.

A separate Unicorn 2.1.4 receipt replays the exact interval in 144 cases.
It visits all 36 sites: 34 ordinary instruction sites execute, while two
growth CALL sites are intercepted. The 32 growth invocations use a recorded
concrete summary: relocate the old element bytes, update begin/end/capacity,
preserve declared state, install sampled volatile outputs, and discard the
already-pushed argument without executing CALL. Old storage becomes
inaccessible until the exclusive stop, catching stale reads after relocation.

An independent ordered-byte oracle checks the entire payload buffer, while
separate guards check the complete object metadata page, protected frame and
registers. A changed external source register must fail the oracle. No growth
helper, allocator or game process executes in this replay.

## Receipts and reproduction

Semantic artifact: `windows_build_13725832_31fe35265598_native_lua_class_vector_append_semantics.json`.
Canonical SHA-256:
`d17dc4796b23572e79a65784de0cc689a0f333005420997461a183c5a022a93c`.
Raw SHA-256:
`ef64ab85719c9764808721a0e99689e75af987a51441553b5b7f0e54e3021495`.

Replay artifact: `windows_build_13725832_31fe35265598_native_lua_class_vector_append_conformance.json`.
Canonical SHA-256:
`f5fad9a1bf7b10cb90fb6731a47906592f80089caa4805592d2ad0e7ce75075a`.
Raw SHA-256:
`c3f752ec1862c41021b3e4e4cc2e2ee1488851d96ab8624328837ce1201b7798`.

`scripts/itb_native_lua_class_vector_append_semantics.py verify` takes
`--executable`, `--evidence`, `--chain` and `--program-facts`.
`scripts/itb_native_lua_class_vector_append_conformance.py verify` takes
`--executable`, `--evidence` and `--semantics`, with Unicorn 2.1.4 available.
Both have a PE-free `verify-structure` command and deterministic stdout
`build` command. Replay tests run the CLI in a subprocess.

The preceding tree/iterator work, real growth behavior, cookie epilogue and
complete owner behavior remain separate work. No whole-program accounting
level is promoted by either receipt.
