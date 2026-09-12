# Native whole insertion with variable byte keys

The complete insertion owner now runs with three order-preserving byte-key
families instead of only fixed-width hexadecimal keys. Each canonical numeric
key is assigned a rank in the union of old keys and the query. The encodings are
injective and strictly preserve unsigned lexicographic order, so the independent
canonical red-black model remains a valid topology oracle.

- Prefix strings contain zero through 31 repeated `a` bytes, covering the empty
  string and shorter-string termination during comparisons.
- Single-byte keys begin at `0x70`, crossing the `0x7f`/`0x80` boundary.
- Long keys share 63 `Q` bytes and differ in their final byte, for 64 bytes before
  the NUL terminator.

Both the construction byte arrays and actual mapped strings are rewritten;
key pointers and their 256-byte storage slots stay fixed. Every terminator is
mapped, padding remains protected, and the whole native insertion receives the
new fixture directly. No comparator, predecessor, insertion, balancing or return
instruction is replaced by a semantic stub. A new node uses one supplied
successful HeapAlloc response; duplicate-key returns allocate nothing.

## Evidence

The 2,826 cases cross all 942 canonical insertion cases with the three string
families. They include 1,746 allocated returns and 1,080 existing-key returns,
with all five owner modes covered. All 69 owner sites execute. The replay uses
the same 1,483 bytes and 580 loaded sites as the prior insertion proof, executing
533 sites. Maximum balancing depth is three iterations and two rotations.
All five ancestor/padding/SEH/local-result/cookie controls pass.

Independent review: **GO**. Focused tests: **24 passed**, including an exact
subprocess rebuild of the entire native corpus. Ordered reads/writes, complete
mapped pages, the pair result, native RET8 and the exact final register/flag
contract are checked by the existing whole-owner machinery.

- [Implementation](../src/observatory/native_tree_byte_key_insert_return_conformance.py)
- [CLI](../scripts/itb_native_tree_byte_key_insert_return_conformance.py)
- [Tests](../tests/test_itb_native_tree_byte_key_insert_return_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_tree_byte_key_insert_return_conformance.json)

Canonical SHA-256:
`ba76ee4b53ab92804bdeef182e6e95c42ad64fb98a80b546f7714d76e2a3a7ff`.
Encoded SHA-256:
`9c0596144b2e7ec9bdf85a57ec5778fe8a9c751e7a497faa29603303851a490a`.

The CLI accepts --program-facts and --insertion-return, with build, verify and
verify-structure commands. Exact operations also require --executable; verify
operations take --evidence. These are finite byte-string families, not a proof
for every possible string, canonical tree, caller, failure or exception.
Whole-program accounting promotions remain zero.
