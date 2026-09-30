# Returned class callback: next integration boundary

This dossier records the enclosing 269-byte returned callback at `0x002ec110`.
Its existing [factory-chain evidence](native_lua_class_factory_survey.md) seals
body SHA-256
`a138a00ca47281aa3b4fb0db11a3aa5e875616a57b3684f7598e4b0517b900e3`
and CFG SHA-256
`c1212e08e59965211c3691fc52551f88f3441ba801bcfa7fe599afcb775dd55b`.
Independent read-only reconstruction rechecked the exact installed PE body on
September 12. The frame facts below formed the integration requirements. The completed
external-spare native receipt is linked below; broader callback domains and
source-level inheritance claims remain open.

## Normal sequence

The callback obtains the destination pointer from Lua upvalue one, index
-10003, and requires it to be nonnull. It calls the native marker helper on
that upvalue and then on argument one. Both branches test **AL**, which matters
because the [marker proof](native_lua_class_marker_conformance.md) preserves
opaque upper EAX bits on metatable paths. Marker truth alone does not establish
the userdata layout or a valid class identity.

Next, lua_touserdata on argument one supplies the source pointer. A local
two-word record contains zero and that pointer. The class operation at
`0x002eb140` receives the destination in ECX and the record address as its
stack argument. Its normal path additionally requires a valid nonnull source
object and the finite tree/vector premises of the selected class proof.

Four lua_rawgeti requests use registry index -10000. The first pair reads
destination+32 and source+32, then calls the table-transfer helper. The second
pair reads destination+40 and source+40, then calls that helper again. The
callback finally copies source word zero to destination word zero and returns
result count zero. Valid registry references, compatible values and normal
Lua responses remain explicit premises.

## Actual native frames

Let C be callback entry ESP and F=C-4. The ordinary body uses ESP=F-36.
Its saved EBP is at F, cookie at F-8, saved EBX/ESI/EDI at F-28/F-32/F-36,
retained destination pointer at F-20, and local record at F-16/F-12.

| Call | Entry ESP | Return continuation RVA |
|---|---:|---:|
| Upvalue lua_touserdata | F-48 | 0x002ec134 |
| Upvalue marker | F-40 | 0x002ec160 |
| Argument marker | F-40 | 0x002ec184 |
| Argument lua_touserdata | F-48 | 0x002ec1a3 |
| Class mutation | F-44 | 0x002ec1bd |
| First destination rawgeti | F-52 | 0x002ec1ce |
| First source rawgeti | F-64 | 0x002ec1d9 |
| First table transfer | F-64 | 0x002ec1e0 |
| Second destination rawgeti | F-76 | 0x002ec1ee |
| Second source rawgeti | F-88 | 0x002ec1f9 |
| Second table transfer | F-40 | 0x002ec203 |

Each rawgeti leaves its 12 bytes of cdecl arguments for later cleanup. The
first table call therefore runs below 24 retained bytes. After the fourth
rawgeti, a 48-byte cleanup restores ESP=F-36 before the second table call.
The class operation uses RET4, restoring that same base after its one argument.

The callback restores nonvolatile registers, checks its cookie, and returns
with EAX=0 and ESP=C+4; the original Lua-state argument remains for its caller.
The cookie call enters at F-28 and overwrites the already-restored EBX save
slot. Under successful checker semantics, ECX is the cookie and EDX retains
the volatile EDX value from the second table helper's final supplied lua_next
response. The normal final
defined arithmetic flags are 0x44. There is no callback-local FS registration;
nested helpers still require their proven registration contracts.

## Completed standalone logical model

The [independent callback model](native_lua_class_callback_semantics.md) now
composes the existing logical class-operation and table-transfer models for
the bounded external spare-vector case. It transfers/overwrites source tree
payloads, appends `[0, source_pointer]`, requests both registry pairs in order,
copies source word zero and returns zero results. Its continuous Lua request
trace retains one argument plus four registry values, with helper prefixes one
and three. The standalone suite passed **125 tests**, including every pair of
category sequences up to length three. Markers, compatible registry values and
normal responses remain explicit premises; this model is not a native callback
execution receipt or a VM/heap behavior claim.

## Continuous external-spare composition

The [continuous callback receipt](native_lua_class_callback_conformance.md) now
executes the callback and all selected normal helper instructions in one
machine across 1,152 finite cases, with one Lua token stack and independent
class/vector/caller output checks. This closes the successful external-spare
composition described below. The subsequent
[continuous growth receipt](native_lua_class_callback_growth_conformance.md)
also executes first-null allocation and full small old-vector copy/free paths
across 2,304 cases. Internal record aliases, larger growth domains and callback
error paths remain open.

## Historical integration requirements

1. Compose helper entries, return addresses, caller registers and preserved ancestor
   stack storage at these actual frames. The marker and table helpers now accept
   checked caller mappings and have focused native cases at these continuations;
   the joined receipt now executes those entries continuously.
2. Use the completed prefix/external spare-vector
   [class record caller mapping](native_lua_class_record_caller_mapping.md):
   this caller supplies F-16 with first word zero. Those helper fixtures now
   accept the actual record and register layout. The
   [first-null and old-full mapping](native_lua_class_growth_record_caller_mapping.md)
   now does so too; internal-record families retain fixed fixtures.
   The joined object pages must also retain
   the registry-reference fields and final word-zero data.
3. Carry one abstract Lua stack across all calls. With one entry argument,
   the first table helper has prefix length one and the second length three.
   The sealed table corpus covers prefixes zero and three; separate actual-caller
   tests now cover prefix one at the first continuation. Both transfers preserve their two
   values: four registry values remain above the entry prefix immediately
   before callback return. Result count zero lets the host handle the frame;
   the native callback does not pop those values itself.
4. Join cookie and nested allocation/FS contracts without skipping native
   helper instructions. The deepest balancing save for the existing class
   mapping is F-240. Validate the entire ancestor stack and object pages,
   including retained rawgeti arguments, against an independent model.

Begin with a bounded successful external spare-vector case, then expand to
existing normal class families. Null/false marker assertions, lua_error,
allocation failure, VM/metamethod behavior and arbitrary object/tree domains
remain separate work. This reconstruction makes no accounting promotion.

## First class-record relocation tranche

The [September 30 helper mapping](native_lua_class_record_caller_mapping.md)
now proves the prefix and external spare-vector cases below, including the
actual incoming registers and independent caller preservation. The
[shared API layout](native_lua_shared_api_layout.md) now provides a common
Lua/heap import and literal contract. The joined receipt now supplies one continuous native run and Lua token state.

The completed helper mapping keeps the existing class stack base: for entry S,
callback F=S+44 and the caller record is at S+28. Its words are zero and
SOURCE_OBJECT, the native argument slot S+4 is S+28, and the real continuation
is `BASE+0x002ec1bd`. This matches the callback's frame relationship without
generalizing every tree/object address. The mapping also checks the actual
incoming registers: EBP=F, EBX=Lua state, ESI=destination, EDI=source,
EAX=record address and ECX=destination. Carry this checked contract into the
eventual joined fixture and nonvolatile-return checks.

The prefix and external-spare fixtures now accept a checked optional `caller`
mapping while retaining the legacy record as their default. Their native
runners consume its argument address, original pair, continuation and
registers. The old prefix and external-spare receipts rebuilt byte for byte
without changing their seals. Existing source/destination object addresses
remain finite premises; arbitrary stack/object relocation is open.

The prefix's independent memory check now restores original caller bytes at
and above S+8 after taking modeled callee scratch pages and preserves the
original eight record bytes. S+8 includes the callback's saved EDI slot. The
spare append model compares against the original supplied pair, not a post-run
read. Actual-record corruption controls require the exact ancestor-memory
rejection. Preserve these independent checks in the continuous callback proof.
