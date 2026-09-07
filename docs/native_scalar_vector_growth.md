# Native growth with larger scalar relocation

The growth helper at RVA `0x002eb620` now executes the native resize,
allocation, feature-zero scalar-copy and deallocation chain for sampled live
sizes four through 256 eight-byte elements. Full vectors grow to
max(size+1, capacity+floor(capacity/2)); spare vectors with capacity 512 return
without changing their storage. Only successful heap API responses are supplied.

Fresh growth prefix and suffix equations rebase the independently sealed scalar
resize oracle at growth ESP G minus 20, replacing its caller return with the
native continuation. Allocation reaches G-96 and free reaches G-88. Both
outcomes consume the unused argument and finish at G+8. The native suffix
restores saved nonvolatile registers and preserves the resize result's flags.
Spare return preserves every payload and object byte, with flags from CMP of
the spare element count against one.

Unicorn 2.1.4 checks 2,880 cases: 1,440 resizes and 1,440 spare returns. Each
resize supplies one allocation and one free response. All 32 block alignments
occur in paired old/new combinations across three stack alignments. The replay
loads 1,083 instruction bytes and 406 sites, executing 261 sites; another 32
bytes of immutable dispatch-table data are verified separately. Complete stack,
payload, metadata, object, feature pages, tables, globals and import slots agree,
as do ordered accesses, registers, defined flags and clear DF. Ancestor and
payload mutations fail at their intended checks. Independent review passed.

This does not cover actual heap effects, failed APIs, SIMD modes, larger live
vectors or arbitrary geometry. No whole-program accounting promotion occurs.

`scripts/itb_native_scalar_vector_growth_conformance.py` accepts the scalar
resize source flags plus `--resize-conformance` and `--growth`, with `build`,
`verify` and `verify-structure` commands. Exact commands require `--executable`;
verification requires `--evidence`. Focused tests include exact CLI rebuilding.

Published receipt:
`windows_build_13725832_31fe35265598_native_scalar_vector_growth_conformance.json`.
Canonical SHA-256:
`74ed35d5c0d666416b1d2d1373c26563464dd54ab97f850225db475c3c967213`.
Raw SHA-256:
`183ce0b2e3128fc4b31d18e9040c571f04d7aec5a0fa5d6e96f1b27904171e94`.
