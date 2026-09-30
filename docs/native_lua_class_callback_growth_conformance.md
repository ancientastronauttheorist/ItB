# Continuous returned-class callback through bounded vector growth

[Implementation](../src/observatory/native_lua_class_callback_growth_conformance.py)
extends the successful returned callback proof to first-null vector allocation
and full old vectors with zero through three live records. The callback, both
markers, tree mutation, growth/allocation, selected old-byte copy/free helpers,
both table transfers and normal cookie checks execute in one Unicorn x86
machine. The [external-spare receipt](native_lua_class_callback_conformance.md)
remains separately sealed with its original output and default contract.

The exact build, 269-byte callback owner and its source pins are unchanged.
The new receipt additionally pins both existing class growth receipts and the
prior callback receipt. Their instruction witnesses supply the complete joined
code union, with every byte overlap checked before execution. Whole executable
SHA-256 and image base are checked before the run and executable identity is
rechecked afterward.

## Finite families and results

Each family pairs all 192 class-prefix vectors with six asymmetric table
profiles. Node/frame layouts, source/destination words, registry references and
opaque upper marker EAX vary under finite recipes. Allocation alignment is
0/7/31. Old-full live/capacity sizes are 0/1/2/3; first-null begins with null
begin/end/capacity. The local record lies above both old and new vector storage.

| Family | Cases | Executed sites | Native instructions | Lua API requests | Allocations | Frees | Assignment requests |
|---|---:|---:|---:|---:|---:|---:|---:|
| First-null | 1,152 | 893 | 1,783,296 | 43,008 | 2,736 | 0 | 1,152 |
| Old-full | 1,152 | 943 | 1,852,992 | 43,008 | 2,736 | 1,152 | 1,152 |

Total: **2,304 cases**, **3,636,288 native instructions**, 945 executed sites,
1,115 selected static sites and 2,905 unique selected bytes. Each family must
execute every normal site inherited from its respective existing class
receipt, every table site and every normal callback site. Callback errors and
the stack-record-inapplicable argument-below-end arm remain excluded.

## Independent state and API contracts

The original vector state comes from actual initial receiver fields. The
[logical model](native_lua_class_callback_semantics.md) opts into the existing
small-vector capacity law: full sizes zero through three grow to one through
four records. Independent final memory reconstructs every original live word,
the original appended `[0,SOURCE_OBJECT]`, and begin/end/capacity fields. It
also checks logical class transfer, payload overwrite, copied source word,
source/reference protection and original parent-owned stack/ancestor bytes.

HeapAlloc and HeapFree share one synthetic target, distinguished by their
exact native call continuation. Tree allocation requests 24 bytes at S-144;
vector allocation requests the logical new capacity times eight at S-140;
free requests the original old pointer at S-132 after all allocations. Both
supplied heap responses remove 16 bytes and preserve mapped pages and
nonvolatile registers. The native allocation, copy and free wrappers execute;
real allocation ownership, freed-memory lifetime and imported DLL behavior
are outside the contract.

Lua APIs keep their supplied normal cdecl contracts. One token-stack interpreter
tracks the actual original argument and four retained registry identities,
checks both helpers' filtering and assignment requests, and agrees with the
independent logical model. Final callback EAX is zero, ESP C+4 and nonvolatile
registers are restored. Host handling of the Lua frame is outside this proof.

## Receipt and controls

[Sealed artifact](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_callback_growth_conformance.json):

- Canonical SHA-256: `59a2123f649633045e35102d2900cf936048f7252095152a27cee6774d60d443`.
- File SHA-256: `b0fb268b5e364c807fd3b62ae5f6716aa137665ba0c24cfd99a01d8d4cd7c723`.
- **26 controls**: 12 first-null and 14 old-full.

Both families reject ancestor/record, copied word, reference, literal/IAT,
appended vector, capacity, result count, retained Lua prefix and heap-request
corruption with exact reasons. Old-full additionally rejects old-buffer byte
and free-request corruption. Each final-cookie control checks the exact native
failure frontier, complete prefix events, register/flag state and mapped pages.

[Tests](../tests/test_itb_native_lua_class_callback_growth_conformance.py) check
the structural seal, per-family code coverage, original records, independent
forged output rejection, actual heap/free frames, Lua identities, strict CLI
encoding and full exact native replay in an isolated subprocess. The
[CLI](../scripts/itb_native_lua_class_callback_growth_conformance.py) uses seven
pinned source receipts and deterministic UTF-8 LF output.

Final validation passed **428 tests, zero skips, in 222.43 seconds**, including
the new conformance suite, both logical suites and byte-identical full native
CLI rebuild. The original external-spare callback suite separately passed
**33 tests in 99.01 seconds**, including its full original byte-identical
receipt rebuild after the shared machinery changes. Independent semantic and
receipt review returned **GO**. All 13 protected original files retained
their baseline hashes.

Assertions, Lua errors, allocation failure, internal record aliases, arbitrary
objects/trees, larger vectors, real VM/metamethod effects and exception dispatch
remain open. This is a bounded normal-return proof with no whole-program
accounting promotion.
