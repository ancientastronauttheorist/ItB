# Conditional assertion owner composition

The three reviewed intervals now account for the complete 315-byte owner
at RVA `0x00379d28`: 78 instruction witnesses, with no gaps or overlap.
Their evidence domains remain distinct. The first is finite exact-prefix
emulation; the second is symbolic argument construction under imported-call
assumptions; the third is an integer model of conditional return paths.

Artifact: `data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_owner_composition.json`.
Canonical SHA-256: `62844b54a1fdbc5b3c466bf9a20e87a1ec91c6f18c0cf5e1f26379fd8fe01dbe`.
Raw SHA-256: `bff4fd11aceaf941d7ea7d79b25da8b23f45e11e2a93a9168475abce4cbbd129`.

| Interval | Bytes | Instructions | Evidence |
|---|---:|---:|---|
| `0x00379d28` to `0x00379e20` | 248 | 55 | Exact prefix, fills and stores on 256 cases |
| `0x00379e20` to `0x00379e37` | 23 | 6 | Conditional symbolic import arguments |
| `0x00379e37` to `0x00379e63` | 44 | 17 | Conditional tail and equality-check model |

This composition joins the complete body witnesses and the stack contracts
at each boundary. It does not turn all modeled inputs into exact executable
tests or constitute an end-to-end native execution of the function.

## Whole-owner relation

The initial helper is selected when the incoming selector differs from
`0xffffffff`. The caller clears and populates the frame, constructs the
import arguments, and conditionally invokes the helper again after the third
import. The second invocation requires both the first and third import
results to be zero, with the same selector condition.

The third import's return is retained in EAX on the modeled direct return
path. EBX and ESI retain entry values, EDI and EBP are restored from saved
words, and ESP becomes entry ESP plus four. If the recovered protected word
differs from the current global comparison word, analysis stops at the
external transfer to `0x00357b6a` instead. This is an open continuation,
not a proof that the function can never return after that transfer.

Imports may change global state. Therefore an initial helper zero-write
does not guarantee that the global still contains zero after those calls.
The post-import helper, when selected, supplies a new four-byte zero effect.
The third import may modify the pair and record buffers, while the declared
saved-state words remain protected.

The generic relation distinguishes selectors sampled by the exact prefix
from additional selectors accepted by the conditional model. It also keeps
current-global equality separate from the earlier seed. These distinctions
prevent a complete byte partition from being mistaken for universal runtime
equivalence.

## Remaining work

The mismatch target already has a structural receipt for 251 bytes and
56 instructions. Its behavior remains the next semantic boundary. Actual
import implementations, nonreturning external behavior, faults, MPX/BND
effects, native object validity and complete game execution remain open.
No whole-program accounting level or exclusion is promoted by this receipt.

The component specifications are in `docs/native_import_handoff.md`,
`docs/native_import_arguments.md`, `docs/native_return_tail.md` and
`docs/windows_exception_layout.md`.

## Reproduction

`scripts/itb_native_assertion_helper_owner_composition.py verify` accepts the
exact `--executable`, `--evidence` and source arguments `--pair`,
`--program-facts`, `--caller`, `--handoff`, `--arguments`, `--tail` and
`--failure-frontier`. Each source is pinned in the receipt. It freshly decodes
the complete owner and verifies the disjoint body partition and interfaces.
Earlier emulation and model matrices are not rerun by this composition tool.

`verify-structure` omits the executable. `build` omits the evidence and emits
deterministic UTF-8 JSON to standard output. No new dynamic executions or
accounting promotions are claimed.
