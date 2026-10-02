# Disjoint inline empty-string copy

The actual-page law in
`src/observatory/native_movement_empty_string_copy_semantics.py` describes the
selected empty assignment in the complete RVA `0x80d0` body. It accepts caller
pages and all eight GPRs and XMMs; it constructs no synthetic fixture and calls
no native helper. Independent source review is GO and all **364 independent
pure tests pass**, without skips.

The source and destination are distinct 24-byte inline strings. Source size is
zero, capacity is 15, and its first byte is zero. Destination capacity is 15
and its old size is at most 15. Caller words install the return address, source
pointer, offset zero and maximum `0xffffffff`. The saved stack span, source
and destination cannot overlap; mapped cross-page spans are supported.

The law predicts exactly 33 instructions and 17 ordered architectural memory
accesses. It clears destination byte zero and its size DWORD, preserving the
other 19 destination bytes and all 24 source bytes. It also predicts all saved
stack writes and reads and preserves every other byte of every supplied page.
Source capacity and its terminator, and destination old size, are **domain
premises rather than native reads** on this branch. Destination capacity is
read twice.

The result has exactly eleven fields: source and destination addresses, full
registers, XMMs, pages, events, defined flags, flag mask, DF, endpoint and trace.
Final EAX is the destination, ECX is zero, EDX is preserved, ESP advances by
16, and nonvolatile GPRs and every XMM are preserved. Defined flags are
`0x85` under mask `0x8d5`, with DF zero. Ordinary entry status flags with the
fixed bit set are admitted; control and reserved flag bits are rejected.

Tests use an independent handwritten instruction/access law and separate full
page prediction. They cover alignment, both source/destination orders, all
128 ordinary flag combinations, every admitted old size, crossing pages,
signed address boundaries, adjacent disjoint spans, exact caller words,
typed input rejection and detached results. Expected output does not come
from production constants or production `apply`.

The complete body contains 288 bytes and 119 decoded sites, SHA-256
`062ae02111f4145fc3b614c93355bc20d6ae59544117d4c8bdcff4d82c488333`.
Provenance pins the program atlas, selected movement binding and default
record native proof. This pure checkpoint does not establish native caller
execution, nonempty or aliased strings, allocation, record append/destruction,
AddMove's ordinary path, gameplay, ownership or whole-game accounting.
