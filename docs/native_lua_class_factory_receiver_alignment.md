# Native factory receiver address adapter

`native_lua_class_factory_receiver_alignment.install` supplies the normal
factory with userdata U=`0x0fffffcc` and allocated record P=`0x10000100`.
These match the existing class-tree receiver and head identities. The embedded
tree pair address is U+52=`0x10000000`; it contains P rather than being P.
This adapter prepares a bounded producer fixture. It does not invoke the
returned closure or execute the class operation.

The adapter first builds the normal complete-factory fixture, then retains
every byte of that extended fixture and adds two previously unmapped writable
pages, `0x0ffff000` and `0x10000000`, filled with synthetic `0xa5`. U's
72-byte extent crosses those pages; P's disjoint 24-byte extent is inside the
second page. The adapter changes only the supplied userdata and heap-result
identity words in fixture metadata. Native factory, initializer, record and
allocation instructions perform all resulting field writes. No generated
tree representation or prebuilt userdata fields are installed.

Eighteen finite vectors combine lengths 0, 16 and 255, high-byte names crossing
their page boundary, distinct name pointers, two caller profiles and three
registry profiles. The original record vector geometry is fixed; the target
allocated head has this one aligned geometry. Other vectors, boolean integer
substitutions and original-page collisions are rejected. Results are detached
from the input page container; page bytes remain immutable.

An isolated native test checks all eighteen complete factory returns using
the same pinned sources and complete physical/Lua oracles as the sealed
normal proof. Actual machine pages and closure identity are captured. Each
return has U+52=P, U+56=0, three self links at P, marker bytes `[1,1]`, and
unchanged `0xa5` padding at P+14 through P+23. U+4, U+8 and U+12 remain zero.
U+24 is the third registry reference, U+32 the first and U+40 the second.
The returned closure carries U. The original unused userdata page and both
original record pages remain unchanged. Four native corruption controls
reject at the exact protected-memory check.

The focused gate passed **27 tests, zero skips, in 3.09 seconds**, including
eighteen actual native successes and four exact controls. The adapter adds no
code to the earlier sealed producer/callback models, changes no receipt, and
promotes no program-wide accounting.

The next class continuation still needs the checked callback frame and a
disjoint valid source representation. Current class fixtures restrict their
entry stack, receiver and source addresses; this address alignment resolves
the receiver/head identities only. Preserve actual U/P bytes, reference
fields and padding while adapting those remaining contracts. Live VM
invocation, class/tree transfer, vector allocation and heap ownership remain
outside this adapter proof.
