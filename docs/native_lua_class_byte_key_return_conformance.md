# Native class return with variable byte keys

The complete class operation now runs with empty/prefix strings, unsigned bytes
across the high-bit boundary, and 64-byte keys sharing 63 leading bytes. A checked
mapping preserves strict key order across the union of source and destination
keys, retaining the independent canonical tree/payload model.

Source strings use 128-byte slots, and source nodes hold their actual rewritten
key pointers. Destination keys keep their existing 256-byte slots. All strings
are NUL terminated and their complete source pages remain protected. Native
insertion, comparisons, successor traversal and payload overwrite are followed
by internal argument reallocation, old-record copying, successful free, append
from the relocated record and the actual cookie-checked return.

## Evidence

The 1,152 cases combine all 192 tree-prefix cases with the first/last record of
a full three-record vector and all three byte-key families. Each family has
384 cases. They perform 3,024 tree iterations (1,584 new and 1,440 existing keys),
1,152 vector allocations and frees, and produce 4,608 final vector records.
The replay loads 2,384 bytes and 924 sites, executing 776 sites. All ten controls
pass. No new code range is needed beyond the sealed internal-growth body.

Independent review: **GO**. All **32 focused tests** were verified across the
initial run and one corrected empty-source-page assertion rerun. The initial
run included exact reproduction of all 1,152 native cases. The implementation
and receipt did not change during the test correction. The separate prefix
mapping suite passed 22 tests, and its original exact receipt remained unchanged.

- [Implementation](../src/observatory/native_lua_class_byte_key_return_conformance.py)
- [CLI](../scripts/itb_native_lua_class_byte_key_return_conformance.py)
- [Tests](../tests/test_itb_native_lua_class_byte_key_return_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_byte_key_return_conformance.json)

Canonical SHA-256:
`cf3cadf46b1a06a4744ccd276ca2c7551a9d1010370cb7e6f24c52ed0b7020f4`.
Encoded SHA-256:
`505ac9eeb3f52f611b329ed22bbe7767705663628b06c88260340ca94b7c163b`.

The CLI derives its source flags from SOURCE_PINS and supports build, verify
and verify-structure; exact operations require the private executable.
The proof retains all prior normal-return premises, including disjoint trees,
small successful vector growth and supplied heap responses. It does not claim
arbitrary strings, unaligned records, failure behavior, actual heap effects,
exceptions or whole-program accounting promotion.
