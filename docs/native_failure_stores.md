# Conditional failure fallback stores

The zero-result branch of the feature query now has an independent global and
stack overlay specification for `[0x00357b83,0x00357c5c)`: 217 bytes and 42
instructions. It stops before the final direct call. The interrupt, final
callee and imported implementations are not executed by this proof.

## Memory and frame contract

G is the failure routine's frame, F-816 relative to the prior owner. Entry
ESP is G-804 and entry EAX is zero. All initial global bytes and newly reserved
locals remain caller-supplied unknowns. The two header words at G and G+4
contain F and the checker continuation; these are not the original owner's
outer return words.

The specification records 22 global writes and seven stack writes, with ten
reads. The global writes affect 76 distinct bytes. Their offsets fit the
independently measured x86 SDK CONTEXT at RVA `0x004b6b78` and
EXCEPTION_RECORD at `0x004b6b28`; see `docs/windows_exception_layout.md`.
The context receives the boundary registers, selectors, flags image, saved
frame and continuation. The record receives code `0xc0000409`, flags 1,
the continuation address, one parameter and parameter value 2.

There is no zero-fill premise. Six selector writes are only two bytes wide;
the upper halves of the corresponding SDK DWORD fields retain their initial
values. Every other untouched byte also retains its supplied value. Matching
field offsets does not establish native object validity or API consumption.

The pushed flags image has known mask `0x000308c7` and value `0x00000046`:
the preceding zero TEST fixes its relevant arithmetic bits, AF remains
undefined, and PUSHFD clears RF/VM in its stored image. Other bits are inputs.
Later arithmetic changes the flags, so final flags are not equated with the
stored image.

The read at `0x00357bef` accesses [G-804] even though its value is overwritten.
It remains in the ordered read oracle and mapped-memory premise. Stack writes
touch twelve distinct bytes: G-808, G-8 and G-4. At the stop, EAX is 4, ECX is
the supplied current global word at `0x00493f24`, and ESP is G-808. Its top
word is the address associated with RVA `0x003f19f8`.

The eight file bytes at that pair location initially identify the two global
record bases. The receipt publishes only their normalized address/hash facts.
It does not assume those values survive loader or runtime changes; this slice
pushes the address without reading the pair's contents.

## Evidence and validation

The 256 integer-model cases cover 16 frame alignments, two input sets, four
compatible pushed-flags images and two arbitrary memory patterns. A separate
ordered oracle checks all 29 writes and ten reads. Three mutation controls
must fail. These are model checks, not emulator or native executions.

Artifact: `windows_build_13725832_31fe35265598_native_assertion_helper_failure_stores.json`.
Canonical SHA-256:
`9c572888c6cf4a50c4bd406c43c60cd455fdd57c59a0a57c0c832bfbbacfd240`.
Raw SHA-256:
`cb12a468a04fd3e2b00609fce5a5d2aefe9f2beed8487f0d7cf2af9c6ac431ca`.

`scripts/itb_native_assertion_helper_failure_stores.py verify` accepts
`--executable`, `--evidence`, `--dispatch`, `--frontier`, `--layout` and
`--program-facts`. It freshly checks the exact instructions, source joins and
file pair witness. `verify-structure` omits the executable. `build` omits the
evidence and emits deterministic UTF-8 JSON to standard output.

Independent tests check field offsets, word widths, unknown-byte retention,
compatible flags, input rejection and receipt mutations. The exact executable
rebuild passes. Imported behavior, termination and the final call remain
outside this receipt; no whole-program accounting level is promoted.
