# Native class vector suffix through caller return

The owner suffix now runs the append at RVA `0x002eb1bb`, its native growth,
resize, allocation, scalar-copy and deallocation descendants, and the owner
cookie epilogue in one state. Execution ends at the real caller return or at
`0x00357b6a` before the external failure implementation. Only successful heap
API responses remain supplied.

The matrix combines the sealed small append domain of zero through three live
elements with sampled larger sizes four through 256. It selects five paired
block alignments and two stack alignments, with two protected cookies and equal
or adjacent current global words. Internal arguments relocate before use;
independent external argument pages retain their original content. Spare vectors
append directly. The tree prefix remains outside this proof.

The append oracle's output registers and complete stack become the input of the
independently sealed return oracle, while original saved register words remain
explicit. With append ESP S and frame F=S+32, saved EDI, ESI and EBX occupy
S, S+4 and S+8; the protected cookie is S+28, outer EBP S+32 and real caller
return S+36. The checker CALL overwrites S+8 after EBX is restored. Equality
finishes at S+44; mismatch preserves S+8. Heap allocation reaches S-104 and
free reaches S-96. API preservation therefore protects the complete ancestor,
including the future cookie comparison and caller return state.

The current cookie at VA `0x00893f28` shares a mapped page with the zero copy
feature word at `0x00893f30`. Full-page verification protects both values. All
other feature pages, tables, import slots, globals, object and payload pages,
external arguments and the complete stack are also checked. Ordered native
accesses, general registers, all defined final arithmetic flags and clear DF
agree with the independent composition. Ancestor and payload controls fail at
the intended memory checks; the ancestor control uses S+40, the consumed
caller argument that normal native execution does not read.

Unicorn 2.1.4 matches 5,920 cases, split into 2,960 caller returns and 2,960
mismatch frontiers. There are 3,000 native resizes, 3,000 allocation and 2,920
free API responses. The replay loads 1,214 instruction bytes and 455 static
sites, executing 304 sites, with 32 table data bytes verified separately. The
filtered alignment matrix does not claim every descendant instruction executes;
all append and return/checker sites do. Independent review passed. Focused
tests include exact CLI rebuilding.

Actual heap effects, failed allocation, the mismatch failure implementation,
SIMD modes, arbitrary geometry and the parent tree prefix remain open. No
whole-program accounting promotion occurs.

`scripts/itb_native_lua_class_vector_suffix_conformance.py` accepts the scalar
append source flags plus `--small-append-conformance`,
`--scalar-append-conformance` and `--return-conformance`. It exposes `build`,
`verify` and `verify-structure`; exact commands need `--executable` and
verification needs `--evidence`.

Published receipt:
`windows_build_13725832_31fe35265598_native_lua_class_vector_suffix_conformance.json`.
Canonical SHA-256:
`3857ad551d3f6577537d379ff7be32d3995f73ca33737745c916cc78883b9b24`.
Raw SHA-256:
`ace4ac1db535271584ebcf7519397a5d9117d21f8698c6a989cb21f2912d018d`.
