# Native class-marker predicate

The 84-byte helper at `0x002eb560` now executes all 32 instructions in Unicorn
through its actual caller return. Its five Lua API implementations are supplied
normal response contracts, with six native call sites. Lua DLL and VM instructions
are not executed by this proof; abstract stack effects and permitted volatile
register outputs are explicit premises.

The helper takes state in ECX and an index in EDX. Without a metatable it returns
EAX=0. Otherwise it pushes the pinned `__luabind_classrep` literal, requests
ordinary `lua_gettable`, converts the result to a Boolean and requests
`lua_settop(-3)`. Both metatable paths restore the entry abstract Lua prefix.
This tests a marker's truth, not native type or class identity.

The return changes only AL on metatable paths. The upper 24 bits of the final
void `lua_settop` EAX survive, so false can return `0xffffff00` and true can
return `0xffffff01`. Native flags are checked per path: the true path retains
its final stack-ADD flags, while false clears AL with XOR. All nonvolatile
registers and the original return word are restored; final ESP is entry+4.

For entry S, API frames occur at S-16, S-16, S-24, S-32 and S-16. Cdecl calls
remove only their return words; three retained argument pairs receive a combined
24-byte caller cleanup. Every IAT read, pushed argument/return word, API frame,
volatile response, normal register result and complete mapped page is checked.
The literal and import pages remain protected under the supplied API contract.

## Evidence

The 576 cases cover all 16 native alignments, two Lua prefix lengths, six
metatable/value profiles and three final void-EAX values. There are 96
no-metatable, 192 false-marker and 288 true-marker cases, with 2,496 supplied
API returns. All 32 sites, six call sites and five imports execute. Seven
mutation controls pass. Independent review: **GO**. All **16 focused tests** were verified across the initial run and one corrected
receipt-mutation test rerun. Exact native CLI reproduction passed in the initial
run; the implementation and receipt did not change during the test correction.

- [Implementation](../src/observatory/native_lua_class_marker_conformance.py)
- [CLI](../scripts/itb_native_lua_class_marker_conformance.py)
- [Tests](../tests/test_itb_native_lua_class_marker_conformance.py)
- [Receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_marker_conformance.json)

Canonical SHA-256:
`d8f146cc7b6666a53348465065e7f6f7768f3d803fb6e4ea38bc9d72662515b9`.
Encoded SHA-256:
`fbfae24cfe5e3ed9affd8ada5add7f04fba3a74ef2d072202e291459734a551e`.

The CLI takes --program-facts and --marker-semantics and supports build, verify
and verify-structure. Exact operations take --executable; verification takes
--evidence. The imported API response contract preserves mapped native storage;
actual Lua heap effects, metamethod execution, errors/nonlocal exits, installed
DLL equivalence and enclosing callers remain outside this proof. No accounting
promotion occurs. The earlier [semantic specification](native_lua_class_marker_semantics.md)
and upstream reference-runtime experiment retain their separate scopes.

## Actual callback mappings

The fixture now accepts an optional caller mapping with entry, return_address,
all eight native registers and complete immutable stack_pages. It validates the
live 32-byte callee scratch interval, original return word, disjoint native
code/endpoint/import/literal storage, uint32 values and nonwrapping RET result.
The native runner accepts the checked fixture and preserves the caller's full
mapped ancestor storage. Default fixture values and the sealed corpus are unchanged.

The [caller-mapping tests](../tests/test_itb_native_lua_class_marker_caller_mapping.py)
passed **31 tests in 9.51 seconds**, including a byte-identical rebuild of the
original 576-case receipt and nine isolated native cases. Those cases exercise
both actual callback continuations, upvalue index -10003 and argument index one,
all three marker paths, caller nonvolatile registers and a crossing-page frame.
Independent review: **GO**. This is helper mapping evidence; it does not execute
the enclosing callback or establish continuity of its Lua state.
