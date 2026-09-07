# Initial HeapAlloc handoff

The candidate thunk at `0x00379f52` (11 bytes/five nodes) tail-jumps to
`0x0038942b` (78 bytes/32 nodes). The initial path through these bodies now
has a strict-u32 specification and exact replay over 19 instruction sites.
It stops before the import CALL at `0x0038945d` or error CALL at `0x00389469`.

The exact PE import table identifies IAT RVA `0x003d6220` as
`KERNEL32.dll!HeapAlloc`. That is static identity evidence. The initial
handoff does not read that IAT slot at runtime and does not execute the API.
It reads the heap-handle global at RVA `0x004b7634` only on the allowed path.

For an unsigned request n, values above `0xffffffe0` go directly to the
error frontier. Other requests pass `max(n,1)` as the byte size, zero as
the flags word, and the supplied global heap-handle word. Heap validity,
allocation success and the error callee's behavior remain unproved.

Let S be entry ESP. The thunk saves and restores EBP before its tail jump.
The wrapper then saves EBP at S-4 and ESI at S-8. At the import frontier,
ESP=S-20 and the three stack arguments, from lowest address upward, are
heap handle, zero flags and normalized size. At the error frontier,
ESP=S-8. EBP is S-4, ESI contains the normalized size or rejected original
size, and other general registers retain entry values.

Oversized requests expose CMP flags. Allowed nonzero requests expose TEST
flags with AF undefined. A zero request executes INC from zero to one and
leaves all six arithmetic flags clear, including the carry preserved from
the preceding TEST. The model checks those distinctions.

## Composition boundary

The earlier allocation-request helper accepts large element counts through
`0x1ffffffb`, producing requests through `0xfffffffb`. This downstream
guard rejects counts `0x1ffffff8` through `0x1ffffffb`, whose byte requests
are `0xffffffe3`, `0xffffffeb`, `0xfffffff3` and `0xfffffffb`.
The largest upstream count reaching the import frontier is `0x1ffffff7`,
with byte request `0xffffffdb`. The four subsequent padding-overflow counts
are a separate earlier failure interval. These statements assume the
forwarded request is unchanged; none specifies the error path's effects.

## Evidence and reproduction

The graph receipt checks 1,440 cases: 448 import frontiers and 992 error
frontiers, with five semantic mutations. The Unicorn 2.1.4 receipt checks
1,776 cases: 288 import frontiers and 1,488 error frontiers, covering every
one of the 31 oversized u32 requests, three heap words and all 16 stack
alignments. All 19 initial-path sites execute. There are no executed CALLs
and no IAT dereferences. The replay deliberately leaves the IAT page unmapped.

The replay compares general registers, defined flags, ordered thunk/frame
and global reads/writes, the full stack and the entire heap-global page.
A changed heap word fails the ordered argument oracle. Independent semantic
and conformance reviews passed. All 58 focused tests passed, including
deterministic exact PE and Unicorn subprocess CLI rebuilds.

`scripts/itb_native_heap_allocation_handoff.py` takes `--program-facts` and
`--retry-semantics`. Its conformance counterpart takes `--semantics`.
Both support `build`, `verify` and `verify-structure`; exact commands need
`--executable`, and verification needs `--evidence`.

Published filenames in `data/observatory/programs/`:

- `windows_build_13725832_31fe35265598_native_heap_allocation_handoff.json`
  — canonical `5571de6ac2e97a838e3919219e7d6459eac8b28b5ec5e3834b9e6f134933fad1`;
  raw `14ee1d52d9a914768b86f0249d1c8d98321965cd2615c4df8c50c65eba264bcf`.
- `windows_build_13725832_31fe35265598_native_heap_allocation_handoff_conformance.json`
  — canonical `51ba7067f55e15a5870b6973f85a94967b2c0586cc5bba91963c155fb7f82958`;
  raw `40f63344e6f843869b95f0fac56ae901f4438c8164ae73ce397f55e39e7348e8`.

Next: the wrapper's full retry/return protocol, including its call-free
retry-flag getter. Imported and error-callee effects still require explicit
premises; no whole-program accounting promotion follows from this handoff.
