# Native default movement effect record

The constructor at RVA `0x001999a0` now has finite continuous conformance
through all seven selected empty-string helper calls and normal RET4. All96
cases execute both exact bodies in one Unicorn state, without API summaries,
helper delegates, allocation, copying or freeing. The broader
[actual-page model](native_movement_effect_record_default_semantics.md) remains
a separate logical domain.

## Domain and actual joins

Six complete pages provide stack, FS, record storage, cookie and empty-literal
witnesses. The96 recipes combine alignment0..15, three nonzero register/XMM/
page profiles and heap versus AddMove-shaped stack-local records. Argument0
is fixed. Stack-local records use `R=S+0x148` and installed return `0x00657397`;
heap records use an external synthetic return. These bind the parent geometry
without executing AddMove itself.

The selected source lies below every inline object and has length zero.
Its helper path never dereferences that source and calls no descendants.
Every case executes356 instructions and217 ordered scalar accesses. Fourteen
physical helper entry/return checkpoints capture all GPRs, all eight XMMs,
raw EFLAGS, defined flags/DF, PC, full-page hashes and event-prefix hashes.
The same machine supplies actual final pages, registers and return endpoint.

The308-byte record has183 written bytes and125 preserved bytes. Exact-width
defaults and duplicate helper size/terminator stores are retained. Full mapped
pages preserve outside documented record, stack and temporary FS writes.
Final EAX is the record, ECX is `cookie XOR(S-4)`, EDX and nonvolatile GPRs
retain their inputs, all XMMs preserve and ESP is `S+8`. The final capacity
comparison produces85 under8D5, raw287 for the fixed incoming246, with DF0.
The constructor saves a cookie; it does not call a cookie checker.

## Receipt and independent checks

Receipt:
`windows_build_13725832_31fe35265598_native_movement_effect_record_default_conformance.json`.

- Canonical SHA256: `942fc246105c941a46ac73e7be432acdacad1428322888b76c0164aca49e673f`.
- File SHA256: `ef954c1f8bdd1672d4b1fd72cf2717f02b93bd9608f9306b987d3ab94bb23c1a`.
- 57,864 bytes, two pins,259 loaded sites/914 bytes and164 executed sites.
- 34,176 instructions,20,832 accesses,672 helper calls and1,344 boundaries.
- 17,568 written and12,000 preserved record bytes; zero promotions.

All173 focused tests pass without skips in79.27seconds. Twelve isolated
workers independently hook the actual single Uc after CPU19 selection, count
all instructions/accesses and inspect all physical boundaries and final state.
The full96-observation hash is independently derived from handwritten pure
oracles. Tests cover typed/model/code/source/receipt forgeries, full rebuild
and exact build/verify/verify-structure CLI commands. All29 controls pass:
26 machine/state mutations and three labeled event/trace-record mutations.
Independent source/CLI and published-receipt reviews are GO.

Use `scripts/itb_native_movement_effect_record_default_conformance.py` with
`--program-facts` and `--movement-binding`. Native commands require the private
exact executable; verification requires evidence. Run isolated gates serially
with the reviewed runtime and disabled faulthandler. Published witnesses are
normalized facts and hashes, never opcode bytes or raw source.

General strings, actual parent execution, record copying/path copying/append/
destruction, AddCharge, failure/unwind handlers, ownership and gameplay remain
open. Real process and hardware execution are excluded.
