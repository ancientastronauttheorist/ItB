# Conditional assertion return tail

The final 44 bytes and 17 instructions of owner `0x00379d28` now have an
independent conditional path specification. It starts at the third imported
call, `0x00379e37`, and covers the caller's final return instruction at
`0x00379e62`. The exact two-instruction small helper and four-instruction
equality checker are included in the analysis.

The integer model passes **1,728 cases**: 864 reach the caller return and 864
reach the checker's external mismatch transfer. The small helper runs in
128 cases. Sixteen Boolean partitions describe the branch decisions. These
are modeled cases over exact decoded operations, not emulator or game runs.

Artifact: `data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_return_tail.json`.
Canonical SHA-256: `fd5c3c19346955ad9a667cdf1f53757fa98f29948f6a26216f431d8e267ec703`.
Raw SHA-256: `b4d31821692dbc968d50e5ad4c6e7c445d5e6b96de19eed747abbb76ff93669e`.

## Decisions and restoration

Let R1 be the first import's return value, R3 the third import's return value,
S the selector at F+8, and F established EBP. The optional helper is called
exactly when `R3 == 0 && R1 == 0 && S != 0xffffffff`. Its selector argument
is not read by the exact tiny body; its observed instruction effect is a
four-byte zero at global RVA `0x004b6e58` under the ordinary integer model.

The caller computes ECX as the protected word at F-4 XOR F, then restores
saved EDI before calling the checker at `0x003574ca`. That checker compares
ECX with the current word at global RVA `0x00493f28`. Equality returns to
the caller; inequality follows an internal conditional edge and the external
jump at `0x003574d5` to `0x00357b6a`.

The current global value need not equal the seed used by the earlier prefix.
Global equality is a separate premise, not a consequence of assuming that
an imported function returns normally.

| Outcome | EAX | ESP | EBP | EDI |
|---|---|---|---|---|
| Equality and caller return | R3 | F+8 | Saved entry EBP | Saved entry EDI |
| Mismatch transfer | R3 | F-812 | F | Saved entry EDI |

At caller return, F+8 is entry ESP plus four, and the instruction target is
the incoming return word at F+4. The equality check preserves the seven
general registers other than ESP on its returning path; its RET advances
ESP by four. Neither the small helper nor the successful check changes EAX.

## External effects and proof limits

The third import is modeled as returning normally with one four-byte stdcall
argument cleaned up. Nonvolatile registers and five words are protected:
saved EDI at F-812, the protected word at F-4, saved EBP at F, the incoming
return word at F+4 and the selector at F+8. The pair and both record buffers
are explicitly allowed to change. Their earlier contents are not used as a
post-import preservation claim.

The model samples all sixteen frame alignments, three values each for R1,
R3 and S, two prefix seeds and both equality outcomes. Selector one is new
to this local model; the earlier exact-prefix replay only sampled selectors
zero and `0xffffffff`. The full tail matrix is therefore not claimed to be
the set of states reached by those earlier exact runs.

Ordinary integer/stack instruction effects and execution without diversion
are premises. MPX/BND prefix effects, hardware faults, actual imported
behavior, nonreturning imports and the external mismatch target's behavior
remain outside this receipt. The older address-selected checker receipt is
unchanged; this follow-up supplies the conditional equality semantics.

## Reproduction

Run `scripts/itb_native_assertion_helper_return_tail.py verify` with the exact
`--executable` and the six source arguments `--pair`, `--program-facts`,
`--arguments`, `--handoff`, `--leaves` and `--reused-check`, plus `--evidence`
for the artifact above. The source identities are recorded in its
`source_receipts`. `verify-structure` omits the executable; `build` omits
the evidence and emits deterministic UTF-8 JSON to standard output. Exact
verification rechecks body and import witnesses and reruns the integer model;
it does not execute the game or any imported implementation.
