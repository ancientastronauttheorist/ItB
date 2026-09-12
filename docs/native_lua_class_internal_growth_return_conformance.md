# Native class operation with internal argument reallocation

The complete class owner now handles a complete aligned argument record inside
a full vector. It transfers the source tree, saves the argument's record index,
grows the vector, copies its old records, frees the old buffer through the
successful API contract, and appends the corresponding record from new storage.
All descendant instructions execute natively between supplied heap responses.

Old sizes/capacities are one, two or three records. Every live record index is
covered. The old vector lives around the original argument on an existing source
metadata page; its live interval is disjoint from the source object, head, nodes
and strings. New storage remains separate from source data and tree allocations.

Before growth, native subtraction and arithmetic shift convert argument-begin
to the aligned index held in EDI. The call at `0x002eb1da` returns to
`0x002eb1df`. After the old buffer is freed, the owner rereads the new begin and
copies the two words at new_begin+8*index. It does not dereference the obsolete
argument address for this append. The independent model copies all original
records, appends the original selected record, and computes begin/end/capacity.

For frame `F=entry-4`, vector HeapAlloc is reached at `F-136`, and HeapFree at
`F-128`. Native growth enters at `F-40` with old begin as the unused stack word.
Final EAX is the source object, ECX the cookie, and EDX the new vector end before
append. Nonvolatile registers restore their incoming values; RET4 finishes at
entry ESP+8. Arithmetic flags are `0x44`, DF is clear and FS state is restored.
The complete old/source page, tree result, new vector, ancestor and globals are
checked alongside the exact ordered memory accesses and API boundaries.

## Evidence

The corpus contains 1,152 cases: 192 tree-prefix cases crossed with every record
index of old sizes one, two and three. It covers both fresh alignments 0 and 31.
The replay loads 2,384 bytes and 924 sites, executing 776. It performs 3,024
tree iterations (1,584 new and 1,440 existing keys), 1,152 vector allocations
and frees, and produces 3,840 final vector records. All ten controls pass.
Focused tests: **27 passed**, including exact CLI reproduction.
Independent semantic review: **GO**.

- [Implementation](../src/observatory/native_lua_class_internal_growth_return_conformance.py)
- [CLI](../scripts/itb_native_lua_class_internal_growth_return_conformance.py)
- [Tests](../tests/test_itb_native_lua_class_internal_growth_return_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_internal_growth_return_conformance.json)

Canonical SHA-256:
`28a3febc6f81de40c0a2ac69270ec3c0a4c71efe5a9f67393915f6ae3f719330`.
Encoded SHA-256:
`bc69a7964f9a4102750f2ea98541c24768750cdbb6208d8e6ac37cb8ba9b115c`.

The CLI derives its source flags from SOURCE_PINS and supports build, verify
and verify-structure. Exact operations require the private executable and are
run in an isolated subprocess.

The successful HeapFree response preserves old bytes in the replay; actual heap
effects are not executed. Unaligned or partial records, larger live vectors,
failed allocation/free, assertion failure, exception delivery, aliased trees
and arbitrary strings remain outside this corpus. Whole-program accounting
promotions remain zero.
