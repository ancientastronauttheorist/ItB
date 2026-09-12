# Class vector owner return and cookie boundary

The owner epilogue at RVA `0x002eb21a` is 19 bytes and **nine** instructions.
It executes the four-instruction cookie checker at `0x003574ca` to either the
owner's caller return or the external mismatch boundary at `0x00357b6a`.
The failure implementation is not executed.

For frame F and preceding append ESP S=F-32, the epilogue reads the protected
cookie at F-4 and saved EDI, ESI and EBX at F-32, F-28 and F-24. It derives
ECX as local cookie XOR F. Its checker CALL then overwrites the already-read
saved-EBX slot at F-24 with continuation `0x006eb227`. This caller-specific
continuation differs from the earlier assertion owner and is explicitly modeled.

Equality with the current global cookie returns through that continuation,
restores EBP from F and the caller return address from F+4, then consumes the
owner argument with RET 4. Final ESP is F+12, or S+44. Mismatch executes the
checker's tail jump and stops before the external failure callee; ESP remains
F-24 and EBP remains F. Both paths preserve entry EAX and EDX, restore saved
EBX, ESI and EDI, and leave ECX equal to the recovered cookie. All six arithmetic
flags come from the final cookie CMP. DF remains unchanged.

The original owner body hash and complete checker witnesses are pinned before
fresh decoding. Unicorn 2.1.4 checks 1,024 cases across all 16 frame alignments,
four cookie words, four global differences, two register seeds and both DF
values. These split into 256 caller returns and 768 mismatch frontiers, covering
all 13 instruction sites and 36 bytes. Ordered accesses, full ancestor stack,
cookie global page, registers and flags match independently derived equations.
A reserved caller-argument mutation exercises full-stack protection; a cookie
mutation on an equal case is rejected for changing the endpoint. Independent
review passed. Focused tests include exact CLI rebuilding.

This checkpoint does not execute the preceding append or tree prefix, initialize
the cookie, or establish failure-handler effects. There is no whole-program
accounting promotion. The nine-instruction epilogue count corrects the earlier
handoff's ten-instruction estimate.

`scripts/itb_native_lua_class_vector_return_conformance.py` provides `build`,
`verify` and `verify-structure` with `--chain`, `--append`, `--checker` and
`--prior-tail` source flags. Exact commands require `--executable`; verification
requires `--evidence`.

Published receipt:
`windows_build_13725832_31fe35265598_native_lua_class_vector_return_conformance.json`.
Canonical SHA-256:
`29a519177fe92e7233cd81556f2b1ab6c3b08cb8136fc5463064d6c48805c060`.
Raw SHA-256:
`e895c0cf6db9790b6759342660d243c5ac74faf8d4bc4f3a2bdd01bc53bd9c9c`.

## Caller relocation

The return relation accepts an explicit `return_address` and the ordered oracle
accepts `stack_base`; both default to the original sealed fixture values. The
stack mapping must contain the complete accessed frame without wrapping. This
lets the enclosing class proof supply its actual stack and caller continuation.
The mismatch endpoint remains the original failure boundary.

Focused default/relocated oracle tests and the original return suite passed
**30 tests**, including byte-identical rebuilding of the existing exact receipt.
Independent review: **GO**. Relocated native execution belongs to the enclosing
class composition; the interface change alone adds no native coverage.
