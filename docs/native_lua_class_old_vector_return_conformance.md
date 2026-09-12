# Native class operation with small old-vector growth

The complete class owner executes tree transfer, growth of a non-null full
vector, copying of its old records, successful old-buffer deallocation, the
external argument append and the actual cookie-checked caller return. Initial
vector sizes and capacities are equal and range from zero to three records.
The new capacities are one through four records.

For class frame `F=entry-4`, growth enters at `F-40` and resize at `F-60`.
Tree-node allocations use the HeapAlloc boundary at `F-140`. The subsequent
vector allocation uses `F-136`, with an eight-, sixteen-, twenty-four- or
thirty-two-byte request. Native copy executes before deallocation: the guard
enters at `F-96`, its free wrapper at `F-108`, and HeapFree at `F-128`.
Exactly one successful HeapFree response follows the vector allocation.

The independent result model preserves the complete canonical tree result,
copies the original live vector bytes to separate fresh storage, appends the
unchanged argument record, and computes the three receiver pointers. The old
page is preserved byte-for-byte by the modeled successful free response. This
is an ABI response contract, not execution of the actual operating-system heap.

Final EAX is the source object, ECX is the cookie, and EDX is `0xb0000001` from
the supplied successful free contract. All nonvolatile registers restore their
entry values; RET4 finishes at entry ESP+8. Arithmetic flags are `0x44`, DF is
clear, and incoming FS registration state is restored. Ordered memory events,
API request/response order, final registers and all mapped data pages are checked.

## Evidence

The 1,536 cases combine 192 class tree-prefix cases, four old sizes and two fresh
alignments. They execute 4,032 tree iterations (2,112 allocations and 1,920
existing-key updates), plus 1,536 vector allocations and frees. Final vectors
contain 3,840 records in total. The replay loads 2,372 bytes and 920 sites,
executing 769 sites. Ten controls include old-storage mutation and an incorrect
HeapFree pointer, alongside ancestor, source, payload, vector, iterator, cookie
and allocation request/result controls.

Independent review: **GO**. Focused tests: **26 passed**, including exact CLI reproduction.

- [Implementation](../src/observatory/native_lua_class_old_vector_return_conformance.py)
- [CLI](../scripts/itb_native_lua_class_old_vector_return_conformance.py)
- [Tests](../tests/test_itb_native_lua_class_old_vector_return_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_old_vector_return_conformance.json)

Canonical SHA-256:
`ebdd6a4cfe4ce14ce5606b183ddea87fd4babafa13adf12e6e6980050c62945a`.
Encoded SHA-256:
`1e21ff2b002f6c56f291289bfb5b2472bd5664672023a0216911b7bd1000424f`.

The CLI derives its source flags from SOURCE_PINS and supports build, verify and
verify-structure. Exact operations require the private executable; exact tests
use a subprocess. This small native copy path does not access feature words or
dispatch tables. The shared allocation/free import page is initialized without
clobbering the other import, and compared in full after execution.

Larger live vectors, internal argument reallocation, allocation/free failure,
actual heap effects, assertion failure, Windows exception delivery, aliased
trees and arbitrary strings remain outside this corpus. Whole-program
accounting promotions remain zero.
