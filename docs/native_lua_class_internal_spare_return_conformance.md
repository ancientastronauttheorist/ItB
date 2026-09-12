# Native class operation with an internal vector argument

The complete class owner now returns after copying a record that already lives
inside its destination vector, while spare capacity avoids reallocation. Source
and destination tree copying remains native, including duplicate-key payload
overwrite, insertion balancing and successor traversal.

The argument is a complete aligned record at the first, middle or last position
of a vector containing one, three or seven records. Its two words still contain
the original class argument and source-object pointer. The surrounding vector
storage shares a mapped page with source metadata but its live/spare records
are disjoint from the source object, head, nodes, strings and tree outputs.

After class tree transfer, the owner subtracts begin from the argument and
converts the positive byte offset to a record index. It checks spare capacity,
reads end and begin again, then copies both words from begin+8*index to end in
order. The independent model appends the original argument record and advances
end by eight, preserving every old record and every protected source/tree byte.

Final EAX is the source object, ECX is the cookie, and EDX is the old vector end.
Nonvolatile registers restore their incoming values; RET4 finishes at owner
entry ESP+8. Arithmetic flags are `0x44`, DF is clear and incoming FS registration
state is restored. The final-cookie mutation still checks the exact first
failure frontier, its ABI, access prefix and protected pages.

## Evidence

The 1,344 cases combine 192 tree-prefix cases with seven size/index pairs:
(1,0), (3,0), (3,1), (3,2), (7,0), (7,3), (7,6). They perform 3,528 tree
iterations: 1,848 allocations and 1,680 existing-key updates. All 30 selected
internal-append/return sites execute; these comprise 74 bytes. The entire replay
loads 1,759 bytes and 683 sites, executing 611. Six negative controls cover the
ancestor, source, payload, vector, iterator and final cookie.

Independent review: **GO**. Focused tests: **24 passed**, including exact CLI reproduction.

- [Implementation](../src/observatory/native_lua_class_internal_spare_return_conformance.py)
- [CLI](../scripts/itb_native_lua_class_internal_spare_return_conformance.py)
- [Tests](../tests/test_itb_native_lua_class_internal_spare_return_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_internal_spare_return_conformance.json)

Canonical SHA-256:
`a81cdc78469e20dda9413247141190d4ffe0b59229aa8123f231d7b4a1c20cbe`.
Encoded SHA-256:
`9d0cd0c59e44c9923758b7827968be72729cff3857164cfd04e05dc73d2f0b39`.

The CLI accepts the same source flags as the external spare-return proof and
supports build, verify and verify-structure. Exact tests replay the executable
in an isolated subprocess. Supplied successful HeapAlloc responses cover tree
nodes only; there is no vector allocation or free on this branch.

Unaligned/partial internal records, internal argument reallocation, failed
allocation, actual heap behavior, assertion failure, exceptions, aliased trees
and arbitrary strings remain outside this corpus. Whole-program accounting
promotions remain zero.
