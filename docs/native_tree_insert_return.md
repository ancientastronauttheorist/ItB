# Whole native tree insertion through return

The complete owner at RVA `0x002e81f0` now runs lower-bound search, duplicate
recognition, successful node construction when needed, native hint dispatch,
canonical balancing, and its final result-pair return in one state. The bounded
corpus covers every one of the owner's 69 instruction sites. Only the successful
HeapAlloc response is supplied; descendant native calls execute normally.

## Caller composition

With owner entry `O`, construction reaches HeapAlloc at `O-96`. The hint enters
at `H=O-40` with result slot `O-8`, lower-bound candidate, new-node key field and
new node. Its balancing child enters at `O-132`, with the deepest save at
`O-148`. The hint restores its synthetic exception registration and cookie,
then returns to `0x002e8270` with ESP `O-20`.

The owner reads the node from `O-8`, writes it to the outer result pair, and
writes one byte `true` at result+4. It restores EDI, ESI, EBX and EBP and returns
with ESP `O+12`. EAX names the outer result, ECX is the cookie, EDX follows the
hint's child result, and defined arithmetic flags are `0x44`; DF is clear.
Existing keys instead return their old node with byte `false`, with no allocation
or hint call. The duplicate path retains its independently derived flag mask.

The independent canonical model checks node links, colors, root, extrema and
count. Explicit fixture output storage lets the child result live on the actual
ancestor stack. Its independent result write follows the ancestor-page copy,
so a forged stack result cannot be masked. Ordered native equations check every
read/write and complete mapped pages, including old strings, payloads, node
padding, globals, output neighbors, ancestor and restored registration.

## Corpus and validation

942 cases cover six tree sizes from one to 31, four construction orders, empty
input, strict minimum/end/interior gaps and existing keys, node/frame alignment,
nil bytes, cookies and previous registration heads. There are 582 inserted
returns (6 empty, 144 minimum, 144 end and 288 interior) and 360 duplicate returns.
The native replay loads 1,483 bytes and 580 sites, executing 533; all 69 sites
of the enclosing owner execute. Child paths reach three balancing iterations
and two rotations. Each inserted case receives exactly one 24-byte HeapAlloc
success response; duplicates receive none.

Five corruption controls fail at the intended checks: unread ancestor data,
new-node padding, restored registration, stack-local result, and the exact cookie
mismatch frontier. Primary independent native-contract review: **GO**.
Focused tests: **24 passed**, including an exact executable CLI rebuild.

- [Implementation](../src/observatory/native_tree_insert_return_conformance.py)
- [CLI](../scripts/itb_native_tree_insert_return_conformance.py)
- [Tests](../tests/test_itb_native_tree_insert_return_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_tree_insert_return_conformance.json)

Canonical SHA-256:
`3fe78f6dac77180f9098dced2624beb51524202e50bed7952de6ec17e20a682b`.
Encoded SHA-256:
`257a147eb0e09c47eff593a534256da6e7ac4f72c8f3e6213047bce3497c6ba7`.

The CLI supports `build`, `verify`, and `verify-structure` with
`--program-facts`, `--construction`, `--empty-hint`, `--extreme-hint`, and
`--interior-hint`. Exact operations additionally require `--executable`;
verification takes `--evidence`. Exact tests use `ITB_EXACT_EXE` and the private
runtime through `PYTHONPATH`.

This closes the finite canonical normal-return corpus, not all trees or
exceptional behavior. Allocation failure, arbitrary hints, fallback dispatch,
actual heap effects, Windows exception delivery, and the enclosing class-owner
composition remain separate. Whole-program accounting promotions remain zero.

## Explicit enclosing-caller mappings

Insertion's lower-bound, decision, construction and final-return oracles accept
caller-provided node addresses, key pointers, query-field address, query pointer
and outer result-pair storage. Defaults retain the original synthetic fixture.
This supports heterogeneous destination nodes and strings retained from source
entries during the enclosing class loop, without global replacements.

Mapping validation checks nonwrapping mapped storage, separate node records,
protected output placement and a fresh allocation disjoint from live ancestors,
existing records, output and source strings. Focused validation passed **19 tests**,
including four isolated native cases with actual relocated pointers and a
caller-local pair. All four existing exact receipts rebuilt byte-for-byte
unchanged, including the final lower-bound metadata revision. Primary review:
**GO**. These explicit mappings add caller flexibility, not broader claims about
arbitrary aliasing or actual heap behavior.
