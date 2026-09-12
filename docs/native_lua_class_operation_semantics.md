# Standalone logical model of normal class mutation

The independent model joins ordered tree transfer, vector record selection,
capacity choice, append and return value. It uses mathematical tree/record
states and does not interpret native instructions or run a native replay.
The supplied source state must correspond to the selected argument record's
nonzero second word; pointer resolution and heap behavior are caller premises.

`apply(source, destination, vector, argument=record)` selects an external
record. `argument_index=index` instead selects one complete record from the
initial vector. The model visits source keys in increasing order, ensures each
destination key exists and overwrites its payload. It appends the selected
record after transfer and returns its second word. Internal selection remains
stable across growth because records are represented by value.

Every input stays unchanged; returned tree, payload and record structures are
detached. A vector has a list of two-uint32 records and a capacity. Spare capacity
is retained. Full vectors grow only in the proven zero-to-three-record domain,
using max(size+1, capacity+floor(capacity/2)). Larger growth is rejected.
Capacities are below `0x10000000`, keeping byte distances in the ordinary
positive signed range; native signed arithmetic at larger spans is not modeled.

Independent review: **GO**. **44 tests passed**. Tests check dictionary-union
payload behavior, ordered copy flags, internal/external selection, detached
state, capacity guards and malformed inputs. Projection tests compare selected
cases from all five full-class native return families: external spare, null
first allocation, non-null old-vector growth, internal spare and internal
growth. Those native proofs separately establish exact memory and ABI behavior.

- [Model](../src/observatory/native_lua_class_operation_semantics.py)
- [Tests](../tests/test_itb_native_lua_class_operation_semantics.py)

This model introduces no new native instruction coverage or accounting
promotion. Failure-side effects, assertions, exceptions, raw memory aliasing,
large growth, Lua object resolution and actual allocation/deallocation remain
outside its contract.
