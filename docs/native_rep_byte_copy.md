# Forward REP byte-copy path

With bit one of the feature word at RVA `0x004b6e48` set, lengths 128 through
2048 can take a separate forward REP MOVSB path. Its bounded contract requires
clear entry DF and destination <= source or destination >= source+length.
Destructive rightward overlap is excluded because it needs backward copying.
The other feature word, SIMD paths and tail tables are not accessed.

The native path transfers bytes in ascending order. Destination receives a
snapshot of the original source, including safe leftward overlap. It returns
destination in EAX, zero in ECX and original length in EDX; nonvolatile registers
are restored and cdecl return advances entry ESP by four. DF remains zero.
Final BT sets CF to one and preserves ZF from comparing length with 128.
OF, SF, AF and PF are undefined at this boundary and are not claimed.

## Evidence and reproduction

The semantic model checks 1,120 cases over all 68 bytes and 23 sites. The
Unicorn 2.1.4 replay checks 1,344 cases over the same sites, with explicit
feature words 2, 3, `0x80000002` and `0xffffffff`. Ordered byte accesses,
complete payload/stack/feature storage, general registers, defined CF/ZF and
DF agree with independent snapshot and memory-access oracles. Negative
controls pass, and no calls or other feature/table accesses execute.

Both independent reviews passed. All 29 focused tests passed, including
exact-executable CLI rebuilds. Other dispatch settings, larger lengths,
backward overlap, DF set and whole-program equivalence remain outside this
checkpoint. No accounting promotion is claimed.

`scripts/itb_native_rep_byte_copy_semantics.py` accepts `--program-facts` and
`--scalar-copy-semantics`; its conformance counterpart accepts `--semantics`.
Both expose `build`, `verify` and `verify-structure`. Exact commands require
`--executable`; verification requires `--evidence`.
Published prefix: `windows_build_13725832_31fe35265598_`.

- `native_rep_byte_copy_semantics.json`: canonical
  `dceee421a6ea8a7a8d172bd479f8cd35bcf138f35195df38889409dc67a21c06`;
  raw `0ec09b0b64a847bcb3d023d74a8fa38792a7922533e2454885c13a19671bec0b`.
- `native_rep_byte_copy_conformance.json`: canonical
  `9bea583a625ac164e8cf26f48c8687f559540ece81db3e90814e2f3d3bb03dfd`;
  raw `3dcc19a7aa68656da195d75802911c8a90e4cb9f22f23dc7525d60036b2f087b`.
