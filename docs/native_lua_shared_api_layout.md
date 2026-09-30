# Shared Lua import and literal layout

Native callback composition now has one checked synthetic layout for HeapAlloc
and thirteen Lua APIs. HeapAlloc retains target `0x05000000`; Lua targets occupy
distinct 256-byte slots starting at `0x05000100`, assigned by sorted API name.
This removes the collisions between the standalone marker/table targets and
the class allocator. Native Lua implementations remain supplied API contracts.

The [layout module](../src/observatory/native_lua_shared_api_layout.py) builds
three immutable synthetic pages: the IAT page and the two literal pages.
HeapAlloc and Lua slots share the IAT page. The marker sentinel and `__finalize`
share a literal page; `__init` occupies the other. All thirteen bindings,
HeapAlloc's binding and all three NUL-terminated literals are validated.

Marker and table fixtures accept `api_layout` alongside their caller mappings.
The supplied layout must contain the complete canonical target map and exactly
the shared page partition. Custom fixtures carry `api_targets`; every direct
oracle/runner path revalidates those targets and shared pages. Caller stack
storage cannot overlap any shared page, including literals unused by that
particular helper. Target-aware expected calls, staged EBX/EDI dispatch and
native hooks use the checked layout. Complete mapped-page comparisons preserve
all sibling fields and padding under the supplied external API premise.

Independent review: **GO**. The [new tests](../tests/test_itb_native_lua_shared_api_layout.py),
original marker/table proofs and both actual-caller suites passed **133 tests in
62.14 seconds**, with zero skips. The new file covers 40 cases. Its isolated
exact native subprocess passed **seven positive cases** and **six protected
memory controls** with exact rejection reasons. The original **576-case marker**
and **320-case table** CLI receipts rebuilt byte for byte. Source receipts and
the executable's pinned digest/image base were checked in the new native run.

Default fixtures, target maps and seals remain unchanged. This prerequisite
allows shared storage to be modeled consistently, but does not by itself run
the enclosing callback or prove one continuous Lua stack. Callback execution,
registry-reference validity, actual Lua DLL/VM behavior, metamethods, errors and
nonlocal exits remain separate proof boundaries. No accounting promotion occurs.
