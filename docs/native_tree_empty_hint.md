# Native empty-tree hint insertion and normal return

This proof joins the empty-tree path of hint owner `0x002e8300` to the real
accepted attachment/balancing child and the normal security-cookie helper.
The 1,600 native cases execute 86 sites out of 232 loaded sites, totaling
641 loaded bytes. All selected hint-owner and cookie-helper sites execute;
the complete accepted balancing child is loaded, although this empty case
needs only its root-attachment and black-parent path.

## Frame and memory contract

Let `H` be the hint owner's entry stack pointer. The owner establishes an
exception-registration record at `H-16`, saving the previous `FS:[0]` value.
The stored handler constant `0x007d0ea0` is opaque and is never dereferenced.
This occurs even on the empty-tree path; it is not deferred to the excluded
fallback wrapper. A synthetic flat 32-bit FS profile maps an isolated page at
zero. Previous registration-head values are arbitrary opaque DWORDs; their
pointees need not be mapped. This does not run a Windows TEB or deliver an
exception.

The owner saves its nonvolatile registers and encoded cookie, prepares five
attachment arguments, and calls the child at `H-92`. The unused child key
argument is the fresh-node address on this path. The child returns with
`ESP=H-68`, writes the supplied result slot, and makes the fresh node the
black root and both head extrema. The hint then restores the previous
registration head before restoring registers. Its cookie call overwrites
the already-restored saved-EBX slot at `H-56` with this caller's continuation
`0x006e84d8`. The final `RET 16` leaves `ESP=H+20`.

Final EAX is the output slot, ECX is the recovered cookie, and EDX and all
nonvolatile registers preserve their entry values. All six arithmetic flags
are `0x44` under mask `0x8d5`, from equality with the stable cookie global at
`0x00893f28`; both DF values preserve. Candidate and key-field arguments at
`H+8` and `H+12` are unread; their pointees are deliberately unmapped.

Every ordered data access and every byte of the complete ancestor, tree,
fresh node, output, registration and cookie pages is checked. The child uses
its independently sealed native oracle with this exact caller frame. Five
node alignments, four frame alignments, five cookies, four saved registration
heads and two nil markers cover the stated 1,600 cases.

Corruption controls separately detect an unread ancestor argument, node
padding, a corrupted restored registration head, and a changed cookie. The
cookie control must stop at exactly `0x003574d5`, before the excluded failure
implementation; an unrelated early stop cannot satisfy that control.

## Boundaries and reproduction

The entire discontiguous hint body is hash checked before selecting the two
normal empty-path ranges. The balancing and cookie points must match their
sealed source receipts. Loaded ranges are `[0x002e8300,0x002e8364)`,
`[0x002e84c0,0x002e84de)`, `[0x0007d0a0,0x0007d294)` and
`[0x003574ca,0x003574d5)`.

- [Implementation](../src/observatory/native_tree_empty_hint_conformance.py)
- [CLI](../scripts/itb_native_tree_empty_hint_conformance.py)
- [Tests](../tests/test_itb_native_tree_empty_hint_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_tree_empty_hint_conformance.json)

Canonical SHA-256:
`eda3e3b090fe4b36b40b2158c3c65767f3604b40574f3a89244c4995a4fde0bf`.
Encoded SHA-256:
`4629b131e3829992605be0e789fad203bc033126c9654dcf2c117dbbb21a618c`.

The CLI accepts `build`, `verify`, or `verify-structure`, with `--program-facts`,
`--balancing` and `--cookie-return`. Exact commands require `--executable`;
verification requires `--evidence`. Enable the gated exact subprocess test
with `ITB_EXACT_EXE` and `.local_decompile/fill_runtime;.` on `PYTHONPATH`.
The exact installed executable retains SHA-256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
No proprietary native bytes are published.

Nonempty hint dispatch, exception delivery/unwinding, the fallback wrapper,
cookie-failure implementation, enclosing construction-owner composition and
whole-game accounting remain open.

Validation: all **41 focused tests passed** across the main run and a
corrected-test rerun, including the exact 1,600-case CLI rebuild. Independent
review of the native frame, registration, cookie and corruption controls: **GO**.
