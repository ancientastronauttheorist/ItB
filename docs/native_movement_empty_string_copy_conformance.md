# Native disjoint inline empty-string copy

The [actual-page empty-string law](native_movement_empty_string_copy_semantics.md)
now has a finite native proof. All **72 independent focused tests pass** without
skips, including twelve independently hooked machine captures, the complete
96-case observation digest, all 26 controls and all three CLI commands.
Independent source, CLI and receipt reviews are GO.

The 96 cases combine all sixteen alignments, three page/register profiles and
two return forms. Both source and destination cross mapped page boundaries.
The return is either an external stop or the installed record-copy continuation
`0x0055ba65`; the caller does not execute in this proof. Old destination sizes
are zero, seven and fifteen. All eight GPRs, eight patterned XMM registers,
ordered events, full pages, defined flags, DF and endpoint are checked.

One CPU19 Haswell Unicorn instance executes the exact body continuously. It
uses no API summary, helper execution delegate or state reseeding. Each case
has 33 instructions and 17 architectural accesses: **3,168 instructions and
1,632 accesses** total. The corpus preserves 2,304 source bytes and 1,824
destination bytes and writes 480 destination bytes. All unrelated page bytes
are preserved apart from the specified saved stack words.

Native prediction checks the complete eleven-field pure packet against a
separate handwritten ABI, full-page, access and trace law before constructing
the machine. The entry record contains actual reads of GPRs, XMMs, raw flags,
PC, page hashes and event-prefix hash. Final checks compare actual full state,
all pages and the complete ordered access and instruction records. Raw finite
VM flags are distinguished from architectural mask `0x8d5` and DF.

The 26 controls include 23 machine/state corruptions and three event/path
record mutations. Wrong entry state, source size, caller words, destination
capacity, preserved bytes and final ABI reject at their intended boundaries.
Record mutations do not prove that their represented writes or instructions
executed. Code substitutions, refreshed point hashes, changed complete model
packets and forged receipts reject before they can authorize a different proof.
Independent observers attach after CPU selection and before native mapping.

The normalized receipt is
`data/observatory/programs/windows_build_13725832_31fe35265598_native_movement_empty_string_copy_conformance.json`:

- Canonical JSON SHA-256: `c3d9d8598d7aa922157397a27a58aeabf86732e9bb620625d602481dd90c18b1`.
- File SHA-256: `29c89a507e53760f49e2de0793e59b9d418ccf5c8829d0ddce211b0abbcf05eb`.
- 34,731 bytes, three source pins, 119 loaded sites, 288 loaded bytes and 33 executed sites.

Use `scripts/itb_native_movement_empty_string_copy_conformance.py` with
`build`, `verify` or `verify-structure`. Program facts, movement binding and
default record are required source flags; executable is required for native
commands. Deterministic UTF-8 LF encoding is part of verification.

Source capacity and terminator, and destination old size, remain domain
premises rather than native reads. General strings, aliases, growth, actual
record-copy callers, AddMove, AddCharge, ownership, gameplay and whole-game
accounting remain open. This proof claims zero child calls, allocation, copy
API requests, frees, opaque instructions and accounting promotions.
