# Actual-page movement record append with existing capacity

The law in `src/observatory/native_movement_effect_record_append2_semantics.py`
describes the selected external-source `0x259f00` append with existing capacity,
eight empty strings and a two-entry path. Independent source review is GO.
All **370 independent checks are validated**, without skips: the initial suite
passed368 checks in53.68seconds and rejected an intended-valid fixture whose
path buffer overlapped its high stack frame. After correcting that geometry
and retaining maximal-pointer coverage separately, all seven affected geometry
checks passed in2.16seconds. Production behavior was unchanged.

`apply` accepts complete immutable pages, all eight GPRs and XMMs, ordinary
DF-clear flags, an installed return word and a supplied allocation result.
The receiver header describes complete308-byte records and has space for the
next record. The external source is at or above the current end and disjoint
from the new record, header, frame, globals and path buffers. Exact schemas,
positive conservative extents and complete mappings are checked. Aliased
source, null end, receiver growth and failure arms are outside this law.

The owner installs the current end into its caller argument word and copies
one record there. Its complete sixteen-field result predicts629instructions,
401ordered accesses,25 helper states, the receiver/source/new-record addresses,
full pages and GPR/XMM state, source/record snapshots and the complete nested
record packet. The reviewed complete record-copy child is trusted internally;
a strict envelope and geometry are checked before adoption. The parent does
not independently recompute every nested field or reject every coordinated
child forgery. The lower record, path, allocator and scalar packets have
separate independent tests.

The new record writes183bytes and preserves125 padding bytes; all308source
bytes remain intact. Its supplied path allocation receives16copied bytes.
Only the receiver end advances by308; begin and capacity preserve. The caller
word remains changed to the old end. Final EAX names the new record, ECX is
the cached cookie XOR entry ESP minus four, EDX is source plus `0xf8`, and ESP
advances by eight. Nonvolatile GPRs and all XMMs preserve. Final defined flags
come from ADD(old end,308) under `0x8d5`, with DF zero. Saved SEH/cookie restore
normally, without cookie checker, exception unwind or failure handler.

Tests handwrite all16 fields, owner and lower traces/accesses,25boundaries and
separate final record/header/caller/stack/page equations. They cover all128
flags, alignments and profiles, crossings, signed/address bounds, adjacent
records, stack-page objects, strict types, child-container substitutions and
detachment. Two private continuous native probes match629instructions,
401accesses,25states and one supplied allocation, including full imported/final
state and vector-end flags. No published native corpus is created here.

The selected owner body is183bytes with SHA-256
`39a9908012609c47f77556aea5af0865f3eb36943b5a1860c4c338bb6ea6fbb7`.
Ten complete selected bodies total1,683bytes. General lengths, nonempty strings,
receiver growth, overlapping copies, allocation failure, destruction, ordinary
AddMove/AddCharge, Lua reachability, gameplay and ownership remain open.
Earlier receipts and whole-game accounting are unchanged.
