# Short scalar overlapping copy

For lengths zero through 31, the copy helper at `0x0036e580` now has a complete
scalar specification and exact replay. The helper's full static body is
1,330 bytes and 404 instructions across twelve discontiguous ranges. This
checkpoint executes only four ranges totaling 171 bytes and 65 sites.
The two excluded four-entry tables are identified and hashed separately.
No feature global, table, REP or SIMD path executes in this short domain.

Readable source and writable destination extents must be nonwrapping and
mapped outside protected stack/code storage. When source < destination <
source+length, the routine copies backward; otherwise it copies forward.
Ordered DWORD transfers handle the bulk, followed by individual remaining
bytes. The resulting destination equals a snapshot of the original source,
including destructive overlap. Zero length performs no payload access.
The exclusive endpoint 2^32 is outside the declared nonwrapping domain.

The cdecl return preserves EBX, ESI, EDI and EBP, advances entry ESP by four,
returns destination in EAX and leaves ECX zero. Backward EDX retains length;
forward EDX is length below four bytes and otherwise the last original source
DWORD read by the forward loop. Both direction-flag values are preserved
because these paths use explicit loads/stores. Final CF, OF and SF are zero;
PF and ZF are one. AF is undefined for a DWORD-multiple length and zero after
a nonempty remainder loop.

## Evidence and reproduction

The semantic model checks 18,432 cases: 13,248 forward and 5,184 backward,
with five rejected mutations. The Unicorn 2.1.4 replay checks 28,672 cases:
21,248 forward and 7,424 backward, with two negative controls. Every short
length, four source alignments, seven overlap/distance choices, all sixteen
stack alignments and both direction-flag values are replayed. Complete stack
and payload bytes, ordered byte/DWORD accesses, general registers, defined
flags and DF are checked against independent snapshot and access oracles.

Both independent reviews passed. All 47 focused tests passed, including
exact-executable CLI rebuilds. This proves the declared short scalar domain;
larger lengths, feature-dependent SIMD/REP paths and complete resize behavior
remain outside this checkpoint. No whole-program accounting promotion occurs.

`scripts/itb_native_small_copy_semantics.py` accepts `--program-facts` and
`--resize-semantics`; its conformance counterpart accepts `--semantics`.
Both provide `build`, `verify` and `verify-structure`. Exact commands require
`--executable`; verification requires `--evidence`.
Published prefix: `windows_build_13725832_31fe35265598_`.

- `native_small_copy_semantics.json`: canonical
  `bc4fa2bd46fd46897897c6096fa7d5f04612a4de810dedbd6423da9c5a0b6319`;
  raw `6829b9b3d1c9d8eb6949beaf0bdd6fe113cc0b6bdfee4a51fb9637b1424ce9bc`.
- `native_small_copy_conformance.json`: canonical
  `59f627925ad50c45ea6add7528137189dc39932582089cce6e381dcb90d485b9`;
  raw `9164c85a63413db73e7d8e03a81e0493551166a9acae498bd43a88de1379aa0b`.
