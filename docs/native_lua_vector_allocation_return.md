# Conditional allocation return tails

The two post-call tails in helper `0x0008a920` now have separate specifications
and exact-byte replays. The large tail `[0x0008a950,0x0008a962)` contains
18 bytes/seven nodes; the small tail `[0x0008a968,0x0008a971)` contains
nine bytes/four nodes. Each begins after an opaque allocator has returned.
They do not prove that allocator's behavior or success.

Let F be the preserved frame pointer and P the post-call EAX value. Entry
ESP is F-4, with saved caller EBP at F and the return word at F+4. Both
tails finish at that return address with ESP=F+12 and restored caller EBP.
Other general registers are preserved relative to the post-call state;
this does not imply the allocator preserved them relative to its own entry.
The graph matrix uses F=`0x03001000` plus 16 alignments. The replay uses
F=`0x02002000` plus four alignments. Frame-wrap behavior is not sampled.

The small tail returns P in EAX and ECX without writing allocation metadata.
Its final arithmetic flags come from adding four to ESP. The large tail
returns Q=`u32(P+35) & ~31` in both registers and stores P in the DWORD
at `u32(Q-4)`. Its final AND leaves AF undefined; the other five arithmetic
flags are checked. The metadata write must be mapped, writable and disjoint
from the protected frame. Aliasing is rejected by this bounded domain.

## Storage geometry and machine words

For an existing writable nonwrapping block of N+35 bytes beginning at P,
with N positive, Q is `32 * ceil((P+4)/32)`. It is 32-byte aligned and
lies between four and 35 bytes after P. Both the metadata word preceding Q
and the N-byte payload beginning at Q fit within the block. This is a
conditional storage result; it makes no allocation-success promise.

The separate strict-u32 relation permits null and wrapping pointer words.
For example, P=`0xffffffdd` yields Q=0 and metadata at `0xfffffffc`, while
P=`0xffffffff` yields Q=32. Such vectors check machine arithmetic and mapped
memory effects. They are not asserted to be usable C++ allocations.

## Evidence and reproduction

The semantic receipt checks 16,384 machine cases, 605 storage-layout cases,
five semantic mutations and a metadata-alias rejection. The independent
Unicorn 2.1.4 receipt checks 792 exact-byte cases over all 11 tail sites.
It compares all general registers, the return address, defined flags,
ordered metadata/return accesses, the complete metadata page and full stack.
Its negative control changes P within the same alignment bucket: the aligned
return stays the same, but the stored original pointer must fail the oracle.

Independent semantic and conformance reviews passed. All 56 focused tests
passed, including exact-executable and Unicorn subprocess CLI rebuilds. No allocator or other
callee instruction executes, and no accounting promotion is made.

The producer `scripts/itb_native_lua_vector_allocation_return_semantics.py`
takes `--program-facts` and `--allocation-semantics`. The corresponding
`itb_native_lua_vector_allocation_return_conformance.py` takes `--semantics`.
Both provide `build`, `verify` and `verify-structure`; exact commands require
`--executable`, and verification commands require `--evidence`.

Published filenames share
`windows_build_13725832_31fe35265598_native_lua_vector_allocation_return_`:

| Receipt | Canonical SHA256 | Raw UTF-8/LF SHA256 |
| --- | --- | --- |
| `semantics.json` | `c759a7f4c53e6382b5a3361ad5971aeaa9cefad21fb8912e05e02b29295af7ff` | `2f23172c1e0992f292995bebb1d7ad962618fc665f3ed4df5de22d9391ef9fc4` |
| `conformance.json` | `681ff7aec2526a193fb0f9c1498dd002e5848d47e9b248186e1a938897327ff6` | `efc2c89d30763b46d122225e00c3d4ca0c74fcef999619ee66e5dcbf15485609` |

Together with the decision receipt, these tails cover 30 of the 34 static
instruction sites under their separate premises. The remaining four are
the two allocator and two failure CALL sites. A complete joined contract
must state their effects, calling convention, frame preservation and
return/nonreturn assumptions explicitly.
