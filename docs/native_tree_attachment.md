# Native tree attachment prefix

This receipt executes the count guard and attachment prefix of `0x0007d0a0`
through `0x0007d0f5`, where balancing begins. Rejected counts stop before
`0x0007d294`; failure cleanup and exceptions remain open.

The private installed executable is hash checked against build
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
The complete containing function is independently decoded against the pinned
program facts before the 85-byte, 35-site prefix is loaded into Unicorn 2.1.4.
All 35 sites execute across 672 cases: 640 attachments and 32 rejected counts.
The receipt stores normalized instruction facts and synthetic vectors only.

## Contract and limits

The unsigned count must be below `0x0aaaaaa9`. Rejection reads only the count
and saves three ancestor registers; no head, node or argument dereference
occurs. Accepted fixtures have zero, one or three reachable existing nodes,
consistent count and head root/minimum/maximum links, a selected sentinel
child, and a fresh disjoint 24-byte node with sentinel child links.

Acceptance increments the count and assigns the new node's parent. Empty-tree
attachment replaces head root and both extrema. Nonempty attachment writes the
selected parent's left or right link, updating that head extremum only when
the parent was its old extremum. Every nonzero selector byte means left.
The root path does not read the selector. The result and key arguments are
unread throughout this prefix. Keys, colors, payload and padding are preserved.

The replay compares every ordered data access, all general registers, all six
arithmetic flags, both preserved direction-flag values, the complete ancestor
stack and all mapped tree/node pages. The last comparison determines flags:
count versus limit on rejection, parent versus head for root attachment, or
parent versus old extremum otherwise. Negative controls deliberately corrupt
an unread ancestor argument and node padding and require the intended full
memory checks to reject both. Frame and node alignments include unaligned
addresses. Rejected fixtures leave node storage unmapped.

This does not prove balancing, node colors, sorted-key attachment correctness,
failure cleanup, exceptions, arbitrary aliasing or whole-game completion.
Global accounting promotions remain zero. It is a standalone prefix proof,
not yet a composition with the insertion hint dispatcher or construction owner.

## Artifacts and reproduction

- [Implementation](../src/observatory/native_tree_attachment_conformance.py)
- [CLI](../scripts/itb_native_tree_attachment_conformance.py)
- [Tests](../tests/test_itb_native_tree_attachment.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_tree_attachment_conformance.json)

Canonical receipt SHA-256:
`7881aafd141fe910567f693c0dbabe8cc17dfc487905a8ac5f331efba21d319a`.
Pretty JSON SHA-256:
`41e5bbdec22c3e7d841d9e4d9f9201ab861117202dae8986b52ab642c7d87098`.

Run the CLI with `build --executable <private PE> --program-facts <pinned facts>`.
It emits deterministic JSON to stdout. `verify` additionally accepts
`--evidence <receipt>` and rebuilds from the executable; `verify-structure`
checks the sealed receipt without the executable. Set `ITB_EXACT_EXE` and the
private Unicorn runtime on `PYTHONPATH` to enable the test's subprocess rebuild.
Independent review approved the native event/flag contract and scope.
