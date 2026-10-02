# Small ordinary path clone semantics

`src/observatory/native_movement_path_small_clone_semantics.py` predicts the
actual-page path clone and reserve composition for zero through 511 entries.
The six keyword-only inputs are pages, GPRs, XMMs, installed return, ordinary
entry flags and one supplied allocation result. Count comes from the actual
source header's end minus begin, divided by eight. Source capacity is unread.
Independent source review is GO. All 594 independent checks pass without skips
in 26.22 seconds. Handwritten dynamic expectations cover complete packets,
all admitted flag combinations, zero/no-runtime and positive branches,
strict geometry, full allocator/scalar forgeries and detachment.

Zero count requires allocation result zero, mapped disjoint headers and the
conservative two-page stack window. Its empty source pointer may be null or
unmapped. No allocator DATA, heap-global or IAT page is required. The parent
and reserve perform six ordered zero header writes and return without any
allocation or scalar-copy call. The trace has 37 instructions and 26 accesses,
with three complete boundary states. Final EAX and ECX identify the destination
header, EDX preserves, ESP advances eight bytes and all XMMs preserve. Defined
TEST flags are `0x44` under `0x8c5`, with explicit DF zero.

Positive counts request eight times count bytes, strictly below 4,096. All
source/destination bytes are mapped, disjoint and nonwrapping. The supplied
successful allocation lies in the declared ordinary DATA region. Heap-global
and IAT values, source/header/frame/runtime separation and exact immutable
page, GPR and XMM schemas are enforced. Counts 512 and above require separate
aligned-allocation machinery and are rejected before invoking primitives.

The complete seven-field ordinary allocator packet is manually predicted and
compared before transporting only its checked final RET event. The complete
ten-field general scalar-copy packet is independently predicted and compared
before adoption. Each owner packet has fifteen fields: geometry, full ABI,
pages, accesses, trace, flags, DF, endpoint, boundaries, allocator/scalar packets,
import and source snapshot. Positive traces have `116 + 10*N` instructions
and `75 + 4*N` accesses, with seven complete boundary states and one import.

Final EAX and ECX identify the destination header and last copied source DWORD
respectively; EDX is source end, ESP advances eight bytes, nonvolatile GPRs
and all XMMs preserve. Source bytes, unread capacity and untouched pages
preserve. Final stack ADD flags use `0x8d5`. SAR3 uses `0xc5`, excluding
undefined AF/OF; imported TEST uses `0x8c5`, excluding undefined AF.

Root executable probes match all 48 old count-two packets and seven actual
full-state cases covering zero, one, two, three, seventeen and 511 entries,
crossing pages and low, signed and high frames. The two-entry result retains
the full fifteen-field compatibility of the prior law. No larger native
receipt, allocator ownership, failure, unwind, Lua or gameplay claim follows.
