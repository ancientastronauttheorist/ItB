# Native attachment through one red-uncle recoloring

The exact installed Windows executable is replayed from `0x0007d0a0` through
attachment, one red-uncle recoloring, and the real `RET 20`. The loaded ranges
are `[0x0007d0a0,0x0007d122)`, `[0x0007d1c0,0x0007d1e3)` and
`[0x0007d272,0x0007d294)`: 199 bytes and 71 sites. The 320-case corpus executes
65 sites, including every site after the sealed attachment prefix. Six
root-attachment sites in that shared prefix are outside this corpus.

## Selected contract

Before insertion, a black root has two red children with sentinel children.
The fresh disjoint red leaf is attached into each of the four available child
positions. The parent and uncle become black, the grandparent temporarily
becomes red, and the cursor ascends to that grandparent. The black sentinel
parent terminates the loop; the return tail makes the root black and writes
the new node through the supplied result slot.

The source attachment oracle supplies its exact prefix effects. Independent
ordered equations describe the new tail, including both fresh ancestry reads
after the parent and uncle color writes. The replay checks every data access,
all general registers, all six arithmetic flags, both DF values and every byte
of the mapped ancestor, tree, node and output pages. ESI is saved at entry
stack minus 16 and restored before the existing return tail. Final EAX is the
result-slot address, ECX the head, EDX the uncle, and ESP entry plus 24.
Nonvolatile registers restore. Final flags come from the head-color byte
comparison with zero. Ancestor-argument and node-padding corruption controls
must fail their intended complete-memory checks.

Five new-node alignments and four frame alignments exercise unaligned storage.
Head color 1 is the canonical black-sentinel case. Head color 255 is also
replayed as a numeric nonzero-branch case, with different sign/parity flags;
it does not assert a canonical red-black tree. An independent rooted-color
checker validates node membership, count, parent links, canonical colors,
red-parent constraints and equal black height before and after the canonical
cases. Key ordering is not inferred from these synthetic storage fixtures.

This proof excludes repeated ascent, rotations, count-failure behavior, the
hint caller, exceptions and a general balancing-loop theorem. No whole-game
accounting promotion is made.

## Evidence and reproduction

- [Implementation](../src/observatory/native_tree_recolor_return_conformance.py)
- [CLI](../scripts/itb_native_tree_recolor_return_conformance.py)
- [Tests](../tests/test_itb_native_tree_recolor_return.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_tree_recolor_return_conformance.json)

Canonical receipt SHA-256:
`5a17fee37ae6ae5d545d70e8268ae80b8b073321bb521339ec8cf989b5a6f6f3`.
Encoded receipt SHA-256:
`18e6461ae59b87e80c19bb0ce732a35bdbf3e107fa4f45181373eef2bc61040e`.

The CLI accepts `build`, `verify`, or `verify-structure` with `--program-facts`
and `--attachment`. Exact commands additionally require `--executable` and
verification requires `--evidence`. Builds emit deterministic UTF-8/LF JSON.
The exact PE hash is
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`;
Capstone 5.0.7 and Unicorn 2.1.4 are the private replay dependencies. Set
`ITB_EXACT_EXE` and `.local_decompile/fill_runtime;.` on `PYTHONPATH` for the
focused subprocess rebuild test. No native bytes or bulk disassembly are
published in the receipt.

Validation: **348 focused tests passed**, including the exact CLI rebuild.
Independent native-contract review: **GO**.
