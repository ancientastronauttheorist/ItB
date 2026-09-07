# Joined vector allocation contract

The allocation owner at `0x0008a920` now joins its request decision, retry
protocol, heap candidate and return tails. This is a conditional contract:
a supplied successful heap response must identify an existing writable,
nonwrapping block of the requested size. No operating-system allocation runs.

Zero count returns zero directly. Small positive counts return the supplied
block pointer. Large successful requests return a 32-byte-aligned payload
pointer and store the original block pointer in the preceding DWORD. Inner
heap failure returns zero to the outer retry loop, whose handler can request
another candidate; it does not become the owner's zero-count return.
Finite transcripts preserve this distinction without claiming termination.
The four counts `0x1ffffff8` through `0x1ffffffb` always reach the candidate
error path under stable requests and cannot produce a positive candidate.
Size and padding failure callees remain open.

## Frame and storage joins

Let A be owner entry ESP. The allocation request is at A-8, retry entry at
A-12, candidate entry at A-24 and heap-wrapper frame at A-28. The actual
HeapAlloc CALL reaches A-48; its supplied stdcall response removes twelve
argument bytes and returns at A-32. Native returns unwind through A-20 and
A-8, and the owner's RET 4 finishes at A+8. Original EBP and nonvolatile
registers are restored. EAX and ECX contain the resulting payload pointer;
EDX comes from the last successful inner heap response.

Allocation blocks and error cells must be disjoint from the entire composed
ancestor stack interval [A-48,A+8), as well as heap, retry-flag and IAT storage.
Opaque responses preserve these words and pushed arguments. The symbolic
frame joins are separate from the component outcome/EAX projections: sampled
volatile values in independent fixtures are not silently equated.

## Evidence and limits

The composition receipt checks four frame joins, 56 allocation contracts,
60 conditional successes and 472 nested protocol cases. It partitions all
34 owner sites into 19 decision sites, 11 tail sites, two joined retry CALLs
and two open failure CALLs. It does not rerun the earlier graph matrices or
claim new whole-program accounting coverage.

A separate integrated Unicorn 2.1.4 replay executes the exact owner, retry,
candidate thunk and heap-wrapper instructions in one machine state. Across
2,576 cases it visits 66 native sites: 16 zero returns and 2,560 supplied
first-attempt heap successes. Samples cover counts 1, 511, 512, 513 and 1024,
all 32 block alignments and all 16 stack alignments. The actual indirect
CALL reads the supplied runtime IAT entry and pushes its native continuation;
the hook stops before any imported instruction and supplies one normal
stdcall response. No allocator instruction executes.

An independent oracle checks all general registers, defined flags, complete
stack, block and global/IAT storage, and ordered native memory accesses.
A changed raw pointer that leaves the aligned result unchanged is still
rejected because the metadata differs. Integrated retry/error paths and
arbitrary counts remain outside this sampled replay; their finite contracts
are recorded separately. Both reviews passed and all 32 focused tests passed,
including exact executable CLI rebuilds.

## Reproduction

`scripts/itb_native_vector_allocation_composition.py` accepts `--program-facts`,
`--allocation`, `--returns`, `--retry`, `--heap-protocol` and `--handoff`.
The conformance CLI accepts `--composition`. Both provide `build`, `verify`
and `verify-structure`; exact operations require `--executable` and verification
requires `--evidence`.

Published receipt prefix: `windows_build_13725832_31fe35265598_`.

- `native_vector_allocation_composition.json`: canonical
  `a63d7ef54e07f8aa63449136988a237592704708ab35cbefb203ec843e8e5507`;
  raw `3225f62121352be3c4498763b3f71c473bbf8533775d2e3becbae3a3caa3dea2`.
- `native_vector_allocation_conformance.json`: canonical
  `8a2af8e009d4f67b672e92e9fd12bce6a5c32feb609af95f2ee1dc61fb1e9d29`;
  raw `583aab3c0d8e90360cc34d6e5d3df998b9fab7ba4931a2bb57daad4c97bd6e74`.

The next owner boundary is vector resize: copying existing payload, guarded
old-storage deallocation and publishing the three vector pointers.
