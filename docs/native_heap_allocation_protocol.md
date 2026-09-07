# Conditional heap wrapper protocol

The candidate thunk, heap wrapper and retry-flag getter now have a complete
finite protocol over 95 bytes/39 instruction sites. This extends the earlier
initial handoff. The flag getter at `0x0038dce2` is six bytes/two nodes:
it reads the stable word at RVA `0x004b7328` and returns. That getter is
modeled directly and executed in the bounded replay.

Requests above `0xffffffe0` proceed to the error accessor. Other requests
normalize zero to one, then call the imported allocation boundary with the
global heap handle, zero flags and normalized size. A nonzero response
returns. A zero response calls the flag getter: zero selects the error
accessor; nonzero calls `0x0038bbc4` with the normalized size. A nonzero
handler response retries allocation, while zero selects the error accessor.

The error accessor at `0x00385bcc` supplies a writable cell pointer. The
wrapper writes 12 into that DWORD and returns zero. The pointer must be
nonwrapping and disjoint from protected frame, global and IAT storage.
The cell's application meaning is not inferred from the constant. Actual
accessor behavior remains outside this contract.

## Explicit external assumptions

The allocation call uses an explicitly supplied runtime IAT target and a
normal stdcall response that consumes 12 argument bytes. Handler and error
responses use cdecl without argument cleanup. These are declared calling
convention and normal-return premises; no operating-system heap call runs.
The supplied responses preserve nonvolatile registers and all modeled
memory, including temporary arguments, original frame words, heap handle,
retry flag and IAT target. Volatile outputs are sampled independently.

The standalone specification accepts at most 64 matching response records.
Missing records require explicit frontier permission, and unused records are
rejected. A failed heap response still executes the flag getter before an
exhausted transcript stops at the next external call. Stable retry state and
finite supplied responses do not imply universal loop termination.

Let F=S-4, where S is entry ESP. Idle wrapper ESP is F-4. The allocation
CALL enters its callee at F-20; stdcall cleanup restores F-4. The flag
getter enters at F-8 and returns without arguments. Handler entry is F-12;
its cdecl return and caller POP restore F-4. Error entry is F-8. Final return
restores ESI and EBP and leaves ESP=S+4. TEST and XOR paths leave AF
undefined; that flag is not claimed on those paths.

## Evidence

The semantic receipt checks 1,792 cases, split between 896 returns and
896 frontier stops. It includes 3,136 opaque normal-return summaries,
1,280 directly modeled flag-getter calls, five semantic mutations and an
error-cell alias rejection.

The Unicorn 2.1.4 receipt checks 1,280 exact-byte cases, equally divided
between returns and frontier stops. It executes all 39 sites, 2,080 external
CALL instructions and 864 complete flag-getter calls. At the external
callee entries, hooks stop before callee instructions and supply the
declared response. The actual indirect CALL reads the supplied IAT word.
No imported allocator, handler or error-accessor instruction executes.

An independent finite-protocol oracle checks general registers, defined
flags, complete stack/global/IAT/error pages and ordered native memory
accesses. Changing the retry flag changes the expected frontier and is
rejected. Independent semantic and conformance reviews passed. All 26 focused
tests passed, including exact-executable and replay subprocess CLI rebuilds.

## Reproduction and remaining composition

`scripts/itb_native_heap_allocation_protocol.py` takes `--program-facts`
and `--handoff`. Its conformance counterpart takes `--semantics`. Both
provide `build`, `verify` and `verify-structure`; exact commands require
`--executable`, and verification requires `--evidence`.

Published files:

- `windows_build_13725832_31fe35265598_native_heap_allocation_protocol.json`
  — canonical `61fbea27f458daf47e0f9aa894999af97829e8080ebbd9b1c596bcb6e8fdb68c`;
  raw `6b839040934a2412e91b8f4661aa9ca9896069e97a7d4243e77691eafaacefc4`.
- `windows_build_13725832_31fe35265598_native_heap_allocation_protocol_conformance.json`
  — canonical `f3a3a2ee0af914a5b23c2bf408d36f529563f275722dabc3a54596549f12d392`;
  raw `7dceb42aed90d1f1f2032556af814feebcdba3630cb861bd9a7368279e71a3b9`.

A joined allocation-owner contract must additionally protect all ancestor
frames from the error-cell and alignment-metadata writes. It must also keep
the inner and outer retry loops distinct: an inner zero return invokes the
outer retry protocol; it is not the allocation owner's zero-count return.
No whole-program accounting promotion or actual allocation success follows
from this conditional wrapper proof.
