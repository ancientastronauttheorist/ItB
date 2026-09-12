# Native class operation with first vector allocation

The class owner at `0x002eb140` now executes native tree transfer, first vector
allocation, the eight-byte argument append and the cookie-checked caller return
when the destination vector initially has three null pointers. Tree insertion,
successor, growth, resize, allocation and zero-byte copy instructions execute
natively. Successful HeapAlloc responses are supplied at their exact ABI boundary.

The vector allocation uses separate storage from every new tree node. For owner
frame `F=entry-4`, growth enters at `F-40`, resize at `F-60`, allocation at `F-88`
and its HeapAlloc boundary at `F-136`; tree HeapAlloc boundaries use `F-140`.
The final request is eight bytes. The independent model retains the complete
canonical tree result, copies the unchanged argument record into fresh storage,
and sets begin/end/capacity to fresh/fresh+8/fresh+8.

Final EAX is the source object, ECX is the cookie and EDX is zero. All nonvolatile
registers restore their original values; native RET4 finishes at entry ESP+8.
Arithmetic flags are `0x44`, DF is clear, and all incoming FS registration state
is restored. Complete source, destination, ancestor and neighboring allocation
storage are compared alongside every ordered native memory access.

## Evidence

The 576 cases combine all 192 tree-prefix cases with vector alignments 0, 7 and
31. They perform 1,512 tree iterations (792 new keys and 720 existing-key
updates), plus 576 first vector allocations. The replay loads 2,213 bytes and
867 sites, executing 719 sites. Eight controls cover the ancestor, source,
payload, vector, iterator, final cookie, allocation request and allocation result.
Independent semantic review: **GO**. Focused tests: **19 passed**, including exact CLI reproduction.

- [Implementation](../src/observatory/native_lua_class_empty_vector_return_conformance.py)
- [CLI](../scripts/itb_native_lua_class_empty_vector_return_conformance.py)
- [Tests](../tests/test_itb_native_lua_class_empty_vector_return_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_empty_vector_return_conformance.json)

Canonical SHA-256:
`557fb53f2566af2f8da35bdb48a1ca7038b0be65e648f696f3d78e978ed06c16`.
Encoded SHA-256:
`0dfb9a8f73f6f3057741f6e9ae7dcb3fffae1012574115a3376f324d709f21ec`.

The CLI derives required source flags from `SOURCE_PINS` and supports `build`,
`verify` and `verify-structure`. Exact operations additionally take `--executable`;
verification takes `--evidence`. Exact tests use the private runtime and
`ITB_EXACT_EXE` in an isolated subprocess.

Nonempty vector growth, internal argument reuse, allocation failure, actual heap
implementation, assertion failure, exceptions, aliased trees and arbitrary
strings remain outside this corpus. Whole-program accounting promotions are zero.
