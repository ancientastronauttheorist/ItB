# Selected normal count-two AddMove law

The law in `src/observatory/native_movement_addmove_normal_semantics.py`
composes selected `0x257340` normal AddMove through default record construction,
empty-destination path assignment, temporary record copy, no-growth append,
two local record destructors, original caller-path free and the actual cookie
checker. It accepts a two-entry owned path with capacity two, eight inline-empty
strings, existing receiver capacity and three supplied ordinary allocation
successes and three successful free responses. Source review is GO. All446distinct
independent checks are validated without skips:443passed in429.01seconds,
two intended-valid fixtures were corrected to respect the external-source
append ordering, and all36affected geometry/domain checks pass in6.39seconds.
The parent now explicitly guards that same selected ordering. The independent
oracle equations are unchanged.

`apply` accepts six keyword arguments: complete immutable pages, all8GPRs and
XMMs, installed return word, ordinary DF-clear entry flags and a three-element
allocation-result list. Its complete fourteen-field result contains geometry,
caller path and raw parameter bits, full final GPR/XMM/pages/events/flags/DF/stop,
2089instruction occurrences,16primary child entry/return states,6actual imported
states and7complete reviewed child packets. The owner contributes70instructions
and43accesses; all composed children bring the total to1293accesses.

Entry ESP is G. The original local record starts at G-0x148, the temporary
record at G-0x27c, and construction/copy/append entry is G-0x290. The deepest
protected frame reaches G-0x338. Every child allocator/free two-page window
must be mapped, as must allocator/error/heap/IAT and FS/cookie/literal pages.
Data spans are disjoint and conservative positive extents must not wrap. The
temporary source must lie at or above the receiver end, preserving the selected
external-source append domain. Other ordering, growth and overlap arms remain
outside this law.

The first allocation copies the caller path into the original record; the second
copies it into the temporary record; the third copies it into the appended
record. Free order is second buffer, first buffer, original caller path. Both
IAT slots name the same synthetic API stop; installed native return words
distinguish allocation and free. The appended record has default type4, mode0
and the caller's raw32-bit parameter at0xc8. Legacy MOVSS zeroes XMM0's upper96
bits; the other seven XMM registers preserve. The receiver end advances308bytes;
begin and capacity preserve. The source path's sixteen bytes preserve despite
supplied frees, which do not unmap storage.

Final EAX is1, ECX is the security cookie, EDX is supplied volatile value
0xb0000001, ESP is G+20, and nonvolatile GPRs preserve. Final flags are0x44 under
0x8d5, with DF0. The actual cookie checker compares the reconstructed value;
normal SEH restore and cookie return execute. Failure and unwind do not.

Reviewed valid child semantics are trusted. Their common envelopes are checked
before adoption: closed typed all8GPR/XMM maps, complete immutable same-page
maps, ordered typed1/2/4-byte accesses, canonical RVA traces and masked flags.
The full eight-field original-caller free packet is independently compared
before rebinding its generic RET/stop to the installed parent continuation.
Every nested semantic field is not recomputed by the parent, and universal
coordinated forgery rejection is not claimed. Child laws have separate
independent tests.

Two private continuous executable probes match all16primary states,6imports,
final full pages/GPR/XMM and all2089instructions/1293accesses. The twenty selected
bodies total3727bytes and1206loaded sites, point anchor
`1a4b2521a802a2dd8c42414f5481c92c820d42708b40f217dd3bbb3a124f54b6`.
A published native corpus is a separate gate. Other path counts, nonempty
strings, growth, failures, ownership, actual Lua invocation, pawn movement and
whole-game decompilation remain open.
