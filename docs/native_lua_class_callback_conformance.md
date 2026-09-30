# Continuous returned-class callback: external spare vector

[Implementation](../src/observatory/native_lua_class_callback_conformance.py)
executes the returned callback at RVA `0x002ec110`, both marker calls, the
complete selected class transfer and external spare append, both table helpers,
and successful native cookie checks in **one Unicorn x86 machine**. Child native
runners are not used to substitute their execution. Existing independently
checked child event laws receive the exact current parent pages and registers;
generated fixture bytes never reset the running parent state.

The enclosing callback body is 269 bytes, SHA-256
`a138a00ca47281aa3b4fb0db11a3aa5e875616a57b3684f7598e4b0517b900e3`.
Its exact source is the installed Windows build `13725832` executable,
SHA-256 `31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
The builder checks the whole executable before and after execution, the image
base, pinned prerequisite receipts and every selected instruction witness.

## Conditional normal scope

Both class markers are true and both userdata pointers resolve valid disjoint
class representations. Registry values are compatible normal values. Lua APIs
have supplied cdecl responses, preserve all mapped pages and nonvolatile
registers, and implement the bounded stack requests. HeapAlloc has a supplied
successful stdcall response; native allocation-wrapper, tree, balancing and
nested FS registration instructions within the selected class path still
execute. Imported APIs, a real Lua VM, metamethod effects and actual heap
ownership are not established by this proof.

The corpus contains all 192 existing class-prefix vectors paired with six
asymmetric table-transfer profiles: **1,152 cases**. Source and destination
trees have zero through seven supplied keys, empty/new/existing/mixed profiles,
node alignments 0/7/31 and frame alignments 0/15. External vector buffers use
two finite addresses, live sizes 0/1/3 and one or two spare records. Marker
void-result upper EAX, source/destination word zero and registry references
vary under finite recipes rather than an additional full Cartesian product.

The local record lies at S+28, where S is the selected class entry stack.
It is above both finite external vector ranges. Consequently the class
argument-below-end arm cannot execute here. Measured unexecuted sites are
exactly `0x002eb1c5`, `0x002eb1c8`, and `0x002eb1ca`; the receipt requires every
other site from the inherited class corpus, every table site and every normal
callback site, and rejects execution of those three sites. This restriction
does not narrow the separate legacy-record child proof.

## Joined checks

Every ordered native memory event, full mapped data page, final general
register and defined arithmetic flag is compared. API handoffs check the
actual target, complete argument words, continuation, ESP and all incoming
general registers. HeapAlloc removes 16 bytes including its return address;
Lua calls remove only their return address. All four rawgeti argument groups
remain until the callback's native 48-byte cleanup.

The independent [logical callback model](native_lua_class_callback_semantics.md)
checks tree/payload transfer, append of the original `[0, SOURCE_OBJECT]`,
copied source word zero and requested assignments. Parent-owned stack cells
and caller ancestors are independently restored from the initial fixture;
source objects, registry-reference fields and other protected pages retain
their original values. Child event laws establish scratch storage below the
parent save area, with separate child structural models checking tree and
vector output.

A single API stack interpreter carries the actual argument and registry
identities across both marker and table helpers. It verifies the complete
request trace against the logical model, including init/finalize filtering.
The final stack has one original argument and four registry values. The native
callback returns EAX zero and ESP C+4, restores EBX/ESI/EDI/EBP, retains the
second helper's supplied EDX and checks its cookie. Subsequent host handling
of the Lua frame is outside this receipt.

## Receipt and validation

[Sealed artifact](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_callback_conformance.json):

- Canonical SHA-256: `e4bc62a4677e0bf190d861cc1749fc0346ee048c8cb39d112ed2c4a36f151cfa`.
- Encoded-file SHA-256: `3ed08f6a7a82749ff1e87b01893849e320844f0a207dc4d0862d8be4609c9218`.
- Selected unique bytes/sites: **2,280 bytes / 874 sites**; executed union **778 sites**.
- Native instructions: **1,611,648**; supplied API requests **43,008**.
- Supplied tree allocations: **1,584**; filtered assignment requests **1,152**.

All ten controls pass: ancestor, local record, copied word, source reference,
literal padding, IAT padding, appended vector record, result count, retained
first registry-pair identity and final-cookie mismatch. Ordinary controls must
fail with their exact expected reason. The cookie control stops at the known
failure frontier `0x003574d5` and checks its exact prefix events, register/flag
state, final mapped memory and preceding complete API trace.

[Tests](../tests/test_itb_native_lua_class_callback_conformance.py) also forge
parent cells and tree output in both joined event pages and child result pages;
the independent models restore the correct original/model values. Exact native
rebuilds run in isolated subprocesses. The
[CLI](../scripts/itb_native_lua_class_callback_conformance.py) provides build,
verify and structural verification using all five pinned source receipts;
noncanonical input encoding is rejected and stdout uses deterministic UTF-8 LF.

The callback conformance, standalone logical model and shared-layout suites
passed **198 tests, zero skips, in 220.04 seconds**, including the full exact
native CLI rebuild with byte-identical output. Independent semantic and receipt
review returned **GO**. The pre-existing 13 protected user files retained their
September 30 baseline hashes.

Assertions, Lua errors, allocation failure, vector growth, arbitrary aliases
and object/tree domains remain open. This is a finite successful external-spare
callback proof and makes **no whole-program accounting promotion**.
