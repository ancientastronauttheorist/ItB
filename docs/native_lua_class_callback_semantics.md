# Returned class callback: independent logical model

[Implementation](../src/observatory/native_lua_class_callback_semantics.py)
composes the existing standalone class-operation and table-transfer models.
It has no dependency on the enclosing callback's native instruction oracle.
Both markers being true, valid disjoint class representations, compatible
registry values and normal Lua responses are explicit premises. This is a
conditional logical model, not VM, heap or native callback execution evidence.

## API and finite scope

```python
apply(source, destination, vector, *, source_pointer, source_word,
      destination_word, destination_refs, source_refs, transfers,
      allow_growth=False)
```

Source and destination use the existing `{"tree": ..., "payloads": ...}`
class representation and its finite tree validation. Their mutable containers
and the vector's mutable containers must be disjoint. The vector has
`records` and `capacity`: zero through three live two-uint32 records, with
strictly spare capacity no greater than five by default. `allow_growth` must be
a strict boolean. With `allow_growth=True`, capacity may also equal the live
record count for sizes zero through three. The existing class-operation law
then grows capacity to `max(size + 1, capacity + capacity // 2)`, giving one,
two, three, or four records of capacity for those full states. Only the
external argument path is modeled. This logical capacity change does not
establish allocation, deallocation, or heap ownership effects.

`source_pointer` is a nonzero uint32. Source/destination word zero and both
two-element registry-reference lists contain strict uint32 values; booleans
are rejected. Numeric reference validation does not prove runtime registry
validity. `transfers` contains two lists, each of at most three categories
chosen from `init`, `finalize` and `other`. The initial Lua argument prefix is
fixed to one value for this tranche.

The returned `class_operation` transfers the source tree in key order,
overwrites existing destination payloads and appends the original record
`[0, source_pointer]`. `destination_word` is the supplied source word zero.
`class_operation.grew` reports whether the input was full; its returned vector
reports the resulting capacity and preserves all original live records.
Opting in with an already spare vector returns exactly the default output.
All output state and request snapshots are detached from inputs and from
separate calls.

## Registry requests and retained Lua values

The stack begins with `[('argument', 0)]`. A fetched registry value is labeled
`('registry', reference)` using the supplied reference itself. Request order is:

| Field offset | First request | Second request | Transfer prefix length |
|---|---|---|---:|
| 32 | destination reference 0 | source reference 0 | 1 |
| 40 | destination reference 1 | source reference 1 | 3 |

Each `registry_requests` entry records its role, field offset, reference and
`lua_rawgeti` arguments `[-10000, reference]`. `calls` contains those four
requests interleaved with both helpers' Lua API requests. Its before/after
stack snapshots form one continuous trace, retaining the actual preceding
argument and registry tokens rather than substituting generic helper prefixes.
Marker/userdata calls, class memory accesses and the final word store are
outside this Lua request trace.

`table_transfers` contains the two helper results with those same actual stack
tokens. `requested_assignments` lists source entry indices categorized as
`other` for each pair; `init` and `finalize` are filtered out. These are
requested assignments, not asserted destination-table or metamethod effects.

Both helpers preserve their destination/source values. Thus `final_lua_stack`
is exactly the initial argument followed by destination-32, source-32,
destination-40 and source-40 registry values, and `lua_stack_delta` is four.
`return_count` is zero. The retained values describe the stack immediately
before callback return; subsequent host handling of the Lua frame is outside
the model.

## Standalone validation

[Tests](../tests/test_itb_native_lua_class_callback_semantics.py) passed
**125 tests in 21.68 seconds**. They cover all 1,600 pairs of category sequences
up to length three, all 14 allowed live-size/spare-capacity pairs, empty/new/
existing/mixed tree profiles, payload overwrites, original-record append,
registry ordering, continuous stack prefixes, zero results, detachment and
invalid-domain guards. These tests do not run a native callback oracle and
make no whole-program accounting promotion.

The [opt-in growth tests](../tests/test_itb_native_lua_class_callback_growth_semantics.py)
add **259 tests** covering all four full sizes, empty/new/existing/mixed tree
profiles, asymmetric table sequences, original-record append, unchanged Lua
requests and zero-result stack contracts, detached results, disjoint mutable
containers, strict boolean opt-in, and malformed inputs. All 14 normal spare
size/capacity states produce exactly the default output when growth is enabled.
The original 125 tests and these 259 tests passed together: **384 passed in
5.10 seconds**. This validation is entirely logical and uses no native callback
oracle, allocator, or real Lua VM.

See the [integration dossier](native_lua_class_callback_integration.md) for
the native frames and the remaining composition boundary.
