# Actual factory receiver through two native callback returns

The factory's actual returned receiver now supports two checked callback
invocations under explicit host invocation and Lua response premises. The first
copies a bounded source into its empty tree and allocates an eight-byte vector.
The second retains verified native return pages and registers, updates the same
source keys' payloads, grows the vector to sixteen bytes, copies the actual old
record, requests free of the old allocation, appends another record and returns.
Both callbacks and all selected helper instructions execute in their respective
continuous x86 machines. Host invocation between machines remains supplied.

Implementation: [native conformance](../src/observatory/native_lua_class_factory_callback_repeat_conformance.py)
and [independent model](../src/observatory/native_lua_class_factory_callback_repeat_semantics.py).
This extends the [nonempty-source first return](native_lua_class_factory_callback_tree_conformance.md).

## Verified state across the second invocation

The finite matrix has 432 cases: eighteen producer profiles, three vector
alignments (0, 7, 31), source populations 0, 1, 3 and 7, and two table-transfer
recipes. Source node alignment is fixed at 31. The first source uses reversed
prefixes of the prior unsigned-key corpus and its disjoint hexadecimal key
storage. The receiver U, sentinel P, closure upvalue, source A, cookie, FS value,
registry references, names and context remain the actual retained values.

The first callback's return capture is accepted only after ordered memory events,
complete mapped pages, Lua identity traces, ABI, fields and tree copy routing
have passed their checks. Before constructing the second host frame, the
adapter requires the captured page digest and all eight captured GPRs to match
the first observation. Capture-page and capture-register controls reject
before running the second callback.

The host patches only the named API/literal bindings, callback entry words,
free import binding, and each source node's payload DWORD XOR `0xffffffff`.
The source keys, links, colors and key pointers remain unchanged. No generated
fixture page replaces retained native pages. The adapter explicitly preserves
U72, P24 and the old eight-byte record across host entry and reuses the first
source word, references and iterator recipes. All other unmentioned captured
bytes survive this boundary; native stack scratch subsequently changes under
checked event laws.

Destination metadata uses the independently modeled first result together with
actual first allocation identities. The second traversal finds every existing
key, preserves its destination node identity and key pointer, and replaces its
payload from the matching source insertion ID. No second-pass tree allocations
occur. Sentinel links and all 24 sentinel bytes remain unchanged.

## Vector growth and free boundaries

The actual old vector is `0x06002000+a`, holding `[0,A]`, size and capacity one.
The new vector is `0x06001000+a`, with sixteen bytes and final records
`[[0,A],[0,A]]`, size and capacity two. The old-vector oracle consumes only the
first two construction pages as new storage and the retained old page as old
storage. Their half-open mapping spans are disjoint; tree nodes in the first
page remain outside the new allocation. Default four-page mappings and prior
receipt behavior are preserved. No global resize mapping is changed.

The shared import dispatch distinguishes allocation continuation `0x00789463`
from free continuation `0x00789172`. Allocation checks its exact sixteen-byte
request, all eight GPRs, T-188 frame and defined TEST flags. Free checks
`[0x00789172,0x12345678,0,old_begin]`, all eight GPRs, T-180 frame and defined
CMP flags under mask `0xcd5`. PF depends on the old pointer low byte, so the
check derives parity for each alignment; the free-flags control corrupts AF. Its supplied successful return checks EAX=1, volatile ECX/EDX response
identities, all remaining GPRs and defined flags at the native continuation.
The class-return EDX is `0xb0000001`, the supplied free response; first-null
EDX=0 is not reused.

Free is a conditional API request with an explicit successful response. The
fixture retains the old bytes; no real ownership transfer, invalidation or
allocator behavior is asserted. Independent record laws check the copied old
pair and the new appended pair, rather than comparing only vector size.

Both callbacks retain actual userdata/source identities in the Lua request
models, filter init/finalize categories, retain five modeled Lua values and
return zero results. Complete return GPRs and defined flags are checked twice.
The repeat model also independently rejects coordinated bad second-call suffix
packets. Its logical native spans require disjoint old8/new16/U72/P24/source72
and the second callback frame; historical first stack scratch may be reused.

## Evidence and remaining work

The 432-case seal selects 1,115 sites in 2,905 unique bytes. Its union executes
797 sites: 76 callback, 623 class-operation, 27 marker and 71 table sites;
318 selected sites are excluded. First calls retain the predecessor's complete
713-site union; second calls execute 546 sites. The union adds 84 sites.
Totals are 286,560 factory, 622,188 first-callback and 520,560 second-callback
instructions; 14,688 factory and 35,424 callback Lua requests; 432 factory,
1,620 first-class and 432 second-class allocations; 1,188 first inserted nodes
and 1,188 second payload updates. There are 432 frees, 3,456 copied old bytes,
6,912 new vector bytes, 1,728 marker and 1,728 table calls, and 864 assignment
requests. All 33 controls pass. Thirty runtime corruption controls cover the inherited return boundaries,
free arguments/GPRs/flags/response identity and retained old bytes. Native cookie
failure stops at the failure boundary before its handler executes; two further
controls guard retained capture identity.

The finite proof covers two invocations and all-existing second source keys.
New second-pass keys require a disjoint node-allocation schedule. More calls,
other source topology, real VM/registry/metamethod behavior, allocator failure,
heap ownership, assertion delivery and whole-program accounting remain open.
No accounting promotion is made.

Receipt: [sealed JSON](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_callback_repeat_conformance.json).
Canonical SHA: `b4b28a9a2f8675705257af3a100f50b72082d1c543a12aff2a5d76e17950966e`.
File SHA: `b2999b07fe273580a4c49a93ec87a008db9decf2e1e67449ab4ed86665094355`.
Deterministic UTF-8 LF size: 389,842 bytes; 31 strictly pinned source receipts.
The CLI supports build, exact verify and PE-free structure verification.
The focused gate passes **260 tests, no skips** (205 model and 55 conformance),
including exact native build and verification. The shared-engine regression
passes **107 tests, no skips**, including unchanged predecessor tree and growth
callback receipt rebuilds. Independent semantic review: **GO**. All thirteen
protected user files retain their baseline hashes.
