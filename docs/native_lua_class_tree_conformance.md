# Native class tree-copy prefix

The class mutation owner at RVA `0x002eb140` now runs its tree phase through
`0x002eb1bb` with native insertion and successor calls in the same state. A
nonzero second argument word names the source object. The owner visits its
source tree in order, ensures each key exists in the receiver's tree, and copies
the source payload DWORD into the returned destination node. It performs that
copy even when insertion reports an existing key.

## Actual caller frames and storage

For owner frame `F=entry-4`, the tree loop runs at ESP `F-32`. Insertion enters
at `F-44`, with result pair `F-20` and query-field address `source_node+16`.
It reaches successful HeapAlloc at `F-140`; balancing can save down to `F-192`.
The owner reloads the returned node, reads source+20 and writes destination+20,
then calls successor at `F-36` with iterator slot `F-8`. Both calls restore the
loop stack. Source and destination node records and strings are disjoint;
new destination nodes retain actual source-string pointers across iterations.

The generic insertion mapping carries node IDs to their actual addresses and
key pointers, including nodes allocated by earlier iterations. No module globals
are replaced. Existing-key iterations allocate nothing; each new key receives
one distinct supplied 24-byte HeapAlloc success response. Every descendant
instruction otherwise executes natively. Source tree, keys and payloads remain
unchanged while the destination's links, colors, count, extrema and payloads
follow the independent class transfer model.

At the prefix endpoint, ESI is the source sentinel, EBX the source object, EDI
the original argument, EBP the owner frame and ESP `F-32`. EAX is the source
sentinel for an empty source, otherwise the iterator slot. Arithmetic flags are
`0x44`, DF is clear, and the owner cookie/local receiver remain preserved for
the vector suffix. Normal nested exception registrations restore before return.

## Corpus and evidence

192 native cases cover source and initial destination sizes zero through seven,
empty/all-new/all-existing/mixed profiles, node/frame alignments, nil markers,
cookies, saved registration heads and payload words. They perform 504 loop
iterations: 264 allocated insertions and 240 existing-key copies, up to seven
iterations per call. The 123-byte prefix has 42 loaded sites; all 36 normal sites
execute, and six assertion-arm sites remain excluded by the nonzero-source
premise. Combined descendants load 1,685 bytes and 653 sites, with 581 executed.

Full mapped pages, every ordered access, final registers and flags agree.
The independent model checks final destination topology, identities, retained
key pointers and payloads. Its final iterator and result-pair writes occur after
the separately checked stack-page copy, preventing those values from validating
themselves. Four corruption controls protect unread ancestor data, source
padding, destination payload and final iterator. Independent review: **GO**.
Focused tests: **26 passed**, including exact CLI reproduction.

- [Implementation](../src/observatory/native_lua_class_tree_conformance.py)
- [CLI](../scripts/itb_native_lua_class_tree_conformance.py)
- [Independent model](native_lua_class_tree_semantics.md)
- [Tests](../tests/test_itb_native_lua_class_tree_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_tree_conformance.json)

Canonical SHA-256:
`0e03dd20ee8451eafd6aa848c8a405e924c38dd6abde121c7c06fdba9ea8358d`.
Encoded SHA-256:
`d52faecaea3de5ca3a6f2bcb1bb416b4a0a02ab909b7f041375f3237cecfa462`.

The CLI supports `build`, `verify` and `verify-structure` with `--program-facts`,
`--class-chain`, `--insertion-return` and `--successor`; exact operations require
`--executable`, and verification requires `--evidence`.

The vector append and whole owner return, assertion failure, aliased trees,
allocation failure, actual heap implementation, exception delivery and arbitrary
strings remain outside this prefix. Whole-program accounting promotions are zero.
