# Native AddMove empty and one-point paths

The AddMove method at RVA `0x00257340` now has finite continuous conformance
for null, owned-empty and one-point paths. All144 cases execute the selected
parent, optional ordinary path free and normal cookie return in one machine.
They return EAX0, preserve all eight XMM registers and restore nonvolatile
GPRs and FS. Count-greater-than-one record work, AddCharge and pawn movement
remain open.

## Finite domain and cleanup

The corpus combines alignments0..15, three page/register/cookie/XMM profiles
and three path forms. Entry stack `G=0x30001000+a`; owned storage
`O=0x06002800+a`. Null has a zero triple. Owned-empty has `[O,O,O+8]`; one
point has `[O,O+8,O+8]`. Nine complete mapped pages are checked, including
unused old storage in null cases. Parameter words vary among negative, NaN
and infinity bit patterns; the native short path never reads them and
executes no SSE or effect-record instruction.

Owned cases free even when their live count is zero: capacity determines
count1/stride8. At guard entry `V=G-0x298`, the installed return is
`0x00657405`. HeapFree enters at `V-32` with
`[0x00789172,0x12345678,0,O]`, without a size word. Its supplied successful
response explicitly preserves full pages, nonvolatile GPRs, all XMMs and
clear DF. Allocation, ownership, unmapping and failure behavior are excluded.
Eight payload bytes remain mapped and unchanged in this bounded witness.

The entire eight-field free packet is checked against the unchanged generic
joined law at the actual frame. Its canonical outer RET event and stop are
rebound only after complete comparison and verification of the actual caller
word. No native helper delegate or fresh machine is used.

## Actual state and flags

Owned cases capture actual free-entry, free-return and cookie-entry packets;
null cases capture cookie entry. Every packet contains complete GPR/XMM,
raw EFLAGS, separately defined flags/DF, PC, full-page and event-prefix hashes.
The import captures the actual full ABI before the supplied response. SAR3
defines maskC5 at free entry, leaving AF/OF unclaimed. Imported pointer CMP
uses8D5; cookie XOR uses8C5, leaving AF unclaimed; final equal-cookie CMP uses
8D5. Normal return has flags44, clear DF and `ESP=G+20`.

Full caller/ancestor, receiver, payload, padding, globals and error pages
preserve outside source-defined stack/FS writes. Null executes42 instructions
and25 accesses; owned paths execute82 instructions and50 accesses. Cookie
corruption rejects at the checked entry boundary; failure-handler execution
is excluded.

## Receipt and independent validation

Receipt:
`windows_build_13725832_31fe35265598_native_movement_addmove_early_return_conformance.json`.

- Canonical SHA256: `c2448f75dc5c50f3e4de7f6bc0f412016cdb07bbe7becc491d5bd1b31f840079`.
- File SHA256: `45374aa188fd76730c0a2c46e16a8762baf9d1046755472684b73ef9cd6ac2fc`.
- 43,401 bytes, five pins,128 loaded sites/401 bytes and82 executed sites.
- 9,888 instructions,6,000 accesses,96 frees, zero allocations/promotions.

All89 focused tests pass without skips:77 in the full gate, then all12 actual
capture workers after correcting observer setup. Observers attach after CPU19
selection and before mapping or execution: installing a hook first initializes
Unicorn's CPU and prevents later model selection. Production and receipt were
unchanged. Independent source/CLI, receipt and observer-fix reviews are GO.

Tests handwrite the full fixture,15-field owner/eight-field child, full pages,
traces, flags and boundaries. Twelve isolated workers independently hook the
actual single Uc, count every instruction/access and read actual final state.
All40 controls pass:37 machine/state and three labeled event/path-record
mutations. Typed/code/source/receipt guards and exact rebuild/CLI are covered.

Use `scripts/itb_native_movement_addmove_early_return_conformance.py` with all
five source paths. Native build/verify require the private exact executable;
verification requires evidence. Run serial isolated gates with reviewed
runtime, disabled faulthandler and `ITB_EXACT_EXE`. General domains and native
game/process/hardware execution are excluded.
