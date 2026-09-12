# Independent class tree-copy model

The tree phase of native class owner `0x002eb140` visits source entries in order,
ensures each key exists in the destination, then copies source payload+20 to the
returned destination node+20. The native continuation does this even when the
insertion result says the key already existed. The following model specifies
that bounded behavior without instruction dispatch or native memory equations.

`native_lua_class_tree_semantics.transfer(source, destination)` accepts two
states containing a canonical red-black `tree` and a parallel list of uint32
`payloads`. It returns a new destination and ordered copy records naming source
and destination IDs, key, inserted flag and payload. Inputs remain unchanged.
Existing destination IDs and topology are preserved for existing-key copies;
missing keys use the independently tested canonical insertion model. Every
source payload overwrites the corresponding destination payload. Source entries
are visited by sorted key, with keys mapped back to stable insertion-order IDs.

The model validates both full trees and payload membership before copying and
rejects a union larger than 256 entries. This is an explicit finite model bound,
not a recovered game limit. An independent dictionary union with source-value
precedence verifies the result in tests, including mixed overlap, differing node
orders, zero/high uint32 keys, repeated transfer, invalid payloads, union overflow
and absence of input/result aliasing.

- [Model](../src/observatory/native_lua_class_tree_semantics.py)
- [Tests](../tests/test_itb_native_lua_class_tree_semantics.py)

Validation: **16 passed**. Independent model review: **GO**. This model alone
claims no native conformance, allocation behavior, memory alias policy, vector
append, exception behavior or whole-game accounting promotion. The native
class-prefix composition is separate work.
