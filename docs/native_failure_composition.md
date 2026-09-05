# Conditional complete failure frontier

The failure routine at RVA `0x00357b6a` now has a checked disjoint partition
of all 251 bytes and 56 instructions. The three component intervals are the
25-byte dispatch, 217-byte fallback stores and nine-byte final call/epilogue.
One static instruction is an exclusive interrupt boundary, leaving 55
instructions in the union of the component models. The 40-byte reporting
wrapper and four-byte owner continuation are recorded separately. The earlier
query thunk remains in the dispatch receipt and is not added to the frontier
denominator.

## Interfaces and remaining conditions

G=F-816 joins the previous owner to this failure frame. A normally returning
feature query with a nonzero result stops before the interrupt with ECX=2,
EAX equal to the query result and ESP=G-804. No interrupt behavior is claimed.

A zero result joins the store specification at ESP=G-804. The stores prepare
the final pair-address argument and stop at ESP=G-808. The wrapper and return
chain then apply only if all four further imports return under their explicit
register and memory summaries. The final EAX is the last wrapper import's
return; the final EBP and target are the current outer words at F and F+4.
Final ESP is F+8.

The return chain needs additional protected header and outer-word intervals,
including the pending status across GetCurrentProcess. These are explicit new
premises. The earlier feature query did not promise to preserve the original
owner's outer words. Pair and record contents remain unspecified after imports.
Neither branch establishes termination or original-word recovery.

This composition checks symbolic frame interfaces and source relationships.
It does not concatenate synthetic component vectors or rerun their matrices.
Their distinct concrete address samples and evidence domains remain separate.
Complete byte coverage does not turn conditional import summaries into actual
Windows execution or whole-program semantic coverage.

## Evidence and reproduction

Artifact: `windows_build_13725832_31fe35265598_native_assertion_helper_failure_composition.json`.
Canonical SHA-256:
`c0355a6465a09de57f596c73594e93ce9dfd5cbc7bb3ad76ab44a06f6da31f6d`.
Raw SHA-256:
`07e9da2406545ed4ee1ae7f917d010cfbcb436622a9cd3b515c4bc3f5d1440ac`.

`scripts/itb_native_assertion_helper_failure_composition.py verify` accepts
`--executable`, `--evidence`, `--dispatch`, `--stores`, `--returns`,
`--frontier`, `--owner` and `--program-facts`. Fresh complete-body witnesses
check the frontier, wrapper and reused owner continuation. `verify-structure`
omits the executable; `build` omits evidence and emits deterministic JSON.

Independent tests check the complete contiguous partition, external-body
separation, interface equations, conditional result classes and invalid words.
The exact executable CLI rebuild is byte-identical. No new model executions,
actual imports, interrupts or accounting promotions are claimed by this receipt.

Component details: `docs/native_failure_dispatch.md`,
`docs/native_failure_stores.md`, `docs/native_failure_return.md` and
`docs/native_owner_composition.md`.
