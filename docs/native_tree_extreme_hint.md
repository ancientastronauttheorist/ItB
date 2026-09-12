# Native minimum and end hinted insertion

This receipt joins two nonempty hint-owner paths to the actual key comparator,
accepted rebalancing child, normal exception-registration restoration and
cookie return. A minimum hint is accepted only when the fresh key is strictly
below every old key. An end hint is accepted only when the fresh key is
strictly above every old key. Equality, interior hints and fallback behavior
are excluded.

The 3,200-case corpus varies four insertion sequences, ten existing sizes
from one to 255, both hint modes, node/frame alignments, DF, saved registration
heads, cookies, nil markers and string alignment. Fixed-width eight-digit
lowercase hexadecimal strings preserve the independently modeled unsigned
key ordering. All string reads execute natively and every byte of the source
pages is protected.

## Caller joins

For owner entry stack `H`, the comparator enters at `H-80`, saves EBP at
`H-84`, and returns to `H-68`. The minimum path compares fresh key against
minimum key; the end path compares maximum key against fresh key. Both strict
comparisons return EAX=1 and ECX=`0xffffffff`. EDX preserves its upper 24 bits
and receives the final compared left byte.

The attachment call reuses those stack bytes. At `H-76`, the unused key
argument is now the comparator classification `0xffffffff`. Parent and
selector are the minimum/left or maximum/right pair. The child enters at
`H-92` with EAX=1, ECX=tree, EBX=output, ESI=extreme, EDI=head and the
comparator's EDX. Its exact oracle and independent canonical insertion model
both run in the real ancestor frame.

The owner preserves the child's EDX result: comparator byte on the initial
black-parent bypass, last uncle after recoloring alone, or old grandparent
after a line rotation. The cookie tail replaces ECX with the cookie and all
arithmetic flags with `0x44` under mask `0x8d5`. Nonvolatile registers restore,
EAX names the result slot and ESP becomes `H+20`. The normal `FS:[0]` record
installation/restoration uses the same explicit synthetic flat-FS premise as
the [empty hint proof](native_tree_empty_hint.md).

## Coverage and boundaries

The loaded code totals 815 bytes and 298 sites; 226 sites execute. All selected
minimum/end owner and normal cookie sites execute. Nine empty-path owner
sites remain loaded but outside this nonempty corpus. Previously sealed
comparator and accepted-balancing bodies are loaded in full without claiming
all their branches occur in this caller.

An extreme insertion follows an all-left or all-right ancestry. It cannot
need a triangle rotation and needs at most one final line rotation; the
experiment enforces those restrictions. Observed repairs need up to two loop
iterations and include non-nil transferred subtrees after recoloring, root
rotations and the permitted nonroot parent-side rotations. Arbitrary balancing
coverage belongs to the [separate accepted-body proof](native_tree_balancing_conformance.md).

Every data access, register, flag and mapped memory byte is compared. Negative
controls corrupt an unread outer argument, node padding, restored registration
head and cookie. Cookie rejection must reach exactly `0x003574d5`, before its
failure implementation. The complete discontiguous hint-owner hash and all
selected child/comparator/checker points are verified against sealed sources.

## Artifacts

- [Implementation](../src/observatory/native_tree_extreme_hint_conformance.py)
- [CLI](../scripts/itb_native_tree_extreme_hint_conformance.py)
- [Tests](../tests/test_itb_native_tree_extreme_hint_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_tree_extreme_hint_conformance.json)

Canonical SHA-256:
`7b3921045dbf9db41fd9f84d8c59167423eed78d2c09071734c9546161b4e37c`.
Encoded SHA-256:
`39f6ac8374c062547ddebb6a8af850eaebba5d66f5398da11673a04a5fa32cc7`.

Use `build`, `verify`, or `verify-structure` with `--program-facts`,
`--balancing`, `--comparator` and `--cookie-return`. Exact commands require
`--executable`; verification requires `--evidence`. The private executable
hash remains `31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Enable exact subprocess tests with `ITB_EXACT_EXE` and the private Unicorn
runtime on `PYTHONPATH`. Published artifacts contain normalized witnesses and
synthetic inputs, never native byte dumps.

Interior hints, equality, the fallback wrapper, exceptions, enclosing
construction composition and whole-game accounting remain open. Independent
native-contract review: **GO**.

Validation: **31 focused tests passed**, including the byte-identical exact
3,200-case CLI rebuild.
