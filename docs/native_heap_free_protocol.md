# Conditional heap-free wrapper protocol

Two five-byte jump thunks at `0x0035785d` and `0x0036fb17` reach the
58-byte wrapper at `0x00389156`. All 68 bytes and 24 instruction sites
now have a finite conditional model and isolated exact replay.

A null pointer returns without calling anything and preserves entry EAX;
it does not synthesize a zero result. A nonnull pointer reaches the statically
verified KERNEL32 HeapFree import with heap handle, zero flags and pointer.
A supplied nonzero result returns. A zero result obtains a writable cell from
`0x00385bcc`, obtains a word through the GetLastError import, calls
`0x00385b53` with that word, stores its supplied result into the cell and returns.
The cell's application meaning and the mapper's implementation remain open.

## External contracts and frames

HeapFree and GetLastError import identities are checked in the exact PE.
Runtime IAT bindings are explicitly supplied and stable; static import names
alone do not prove runtime binding. The actual indirect CALLs and their IAT
reads execute in replay, but no imported or other opaque callee instruction
executes. HeapFree responses consume twelve argument bytes; GetLastError
consumes zero, and the accessor and mapper use cdecl with no argument cleanup.

All responses preserve nonvolatile registers and modeled memory, including
pushed arguments, saved frame words, heap handle and IAT cells. The error cell
must be nonwrapping and byte-disjoint from protected storage and modeled code.
At most four matching responses are accepted. Missing responses require
explicit frontier permission; unused or out-of-order responses are rejected.
A frontier stops before its CALL and before any associated IAT read.

Let S be thunk entry ESP. HeapFree enters at S-20 and its supplied stdcall
return restores S-4. The error path saves ESI; accessor and GetLastError
enter at S-12, while mapper enters at S-16. The final POP ECX recovers the
GetLastError word. EAX is the mapper result, ESI and EBP are restored, and
cdecl return leaves ESP=S+4. Null return has six CMP-defined flags; heap
success has TEST flags with undefined AF excluded. Error return retains the
mapper's sampled flags because no later native instruction changes them.

## Evidence

The semantic receipt checks 736 cases: 544 returns and 192 frontiers, with
2,112 supplied calls, five mutation controls and an IAT-alias rejection.
The Unicorn 2.1.4 receipt checks 1,472 cases: 1,088 returns and 384 frontiers,
with 4,224 actual CALLs into excluded targets and two negative controls.
All 24 sites and 16 stack alignments are covered. Independent oracles check
all general registers, defined flags, complete stack/global/IAT/error pages
and ordered native memory accesses. Both independent reviews passed and
all 35 focused tests passed, including exact-executable CLI rebuilds.

No operating-system free effect, actual allocation lifetime, error-accessor
or mapper implementation, game execution or accounting promotion follows
from these supplied normal-return contracts.

## Reproduction

`scripts/itb_native_heap_free_protocol.py` accepts `--program-facts` and
`--deallocation-semantics`; its conformance counterpart accepts `--semantics`.
Both expose `build`, `verify` and `verify-structure`. Exact commands require
`--executable`; verification requires `--evidence`.
Published prefix: `windows_build_13725832_31fe35265598_`.

- `native_heap_free_protocol.json`: canonical
  `768d063a914e392138cb584fc50049b6481d545b8f58a49eca18bd85bcfafca5`;
  raw `0ecb936d164d386b8bdb160afef1958fdc3516536778ad5b71df9117e41179fa`.
- `native_heap_free_protocol_conformance.json`: canonical
  `c2e07687b933726d0f64cb0c01898468a54ef2aecb4de5e01125f3b8809ad3a3`;
  raw `6d1aa742905ad955c74df652518be8d13c66a3c2b8195e07134725d8c0fc8a38`.

Joining the vector deallocation guard must additionally protect all ancestor
arguments and frames from the error-cell write and execute the guard's
three-instruction return tail.
