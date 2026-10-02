# Native empty-path movement record copy

The [actual-page record-copy law](native_movement_effect_record_empty_copy_semantics.md)
has a finite native proof for eight empty inline strings and an empty path.
Independent harness, CLI and receipt source reviews are GO. All **81 independent checks pass**, without skips: the initial suite passed
80 in234.12seconds; a source-corruption test was a no-op, then all eight
fixture checks passed in0.83seconds after changing it to flip the existing
byte. Production code and receipt were unchanged by that test correction.

Forty-eight cases combine sixteen alignments and three complete page/register
profiles. Both 308-byte records cross mapped page boundaries. One CPU19
Haswell Unicorn instance executes the owner, eight empty-string helpers,
zero-count path clone and reserve continuously. No helper is delegated to
another native process; no allocation, copy or free response is supplied.

Each case executes 492 instructions and 315 architectural accesses. The
corpus checks 23,616 instructions, 15,120 accesses and 1,008 actual boundary
snapshots. All eight GPRs and XMMs, full pages, ordered event prefixes,
defined flags, DF and PC are read at outer entry and twenty helper boundaries.
Final state and every access and trace site are checked against the model.
The records preserve all 308 source bytes and 125 destination padding bytes,
while writing 183 destination bytes. Across the corpus those counts are
14,784 source bytes preserved, 6,000 padding bytes preserved and 8,784 bytes
written. Scalar bit patterns are copied without interpreting their meaning.

The complete fourteen-field model packet is checked before machine creation
against separate record, stack, boundary and ABI equations and the literal
trace. Model access replay establishes typed counts and page consistency;
actual online checks and independent handwritten test oracles establish the
complete ordered accesses. Replay alone does not reject every coordinated
same-count event forgery. Raw finite VM flags are recorded separately from
architectural masks and DF. Outer entry uses raw `0x246`, whose defined flags
are `0x44` under `0x8d5`; the initial harness mask mismatch was corrected.

The 58 controls exercise seven boundary roles across five state classes,
actual first reads, preserved bytes, final ABI and three record mutations.
A changed record is not evidence that its represented operation executed.
Independent observers install after CPU selection and capture all 21 actual
states. Exact source and executable pins, complete bodies, refreshed points,
model contracts, receipt encoding and CLI commands are independently checked.

The normalized receipt is
`data/observatory/programs/windows_build_13725832_31fe35265598_native_movement_effect_record_empty_copy_conformance.json`:

- Canonical SHA-256: `e7a534fde897fc1e7520c1de8e8d7f9bb2a7fad6a33520c3fc70f396fe8c024d`.
- File SHA-256: `f4ac5009002ffcbf107b50fc4b92958b92d6b4918852bff2ebb068dd504706dc`.
- 79,638 bytes, four source pins, 386 loaded sites, 1,226 loaded bytes and 261 executed sites.

Use `scripts/itb_native_movement_effect_record_empty_copy_conformance.py` with
`build`, `verify` or `verify-structure`. Required sources are program facts,
movement binding, default-record conformance and empty-string conformance.
Native commands also require the exact executable. Encoding is UTF-8 LF.

FS base zero, eight source strings with size zero, capacity fifteen and a NUL
first byte, and the zero source-path triple are premises. Some premise fields
are unread by the selected path. Saved SEH and cached cookie restore normally;
no cookie checker, failure handler or exception unwind executes. Nonempty
strings or paths, record assignment, append, growth, destruction, normal
AddMove, AddCharge, Lua reachability, gameplay and ownership remain open.
No opaque instructions or whole-game accounting are promoted by this proof.
