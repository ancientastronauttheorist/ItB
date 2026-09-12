# Returned class callback: next integration boundary

The next enclosing owner is the 269-byte returned callback at `0x002ec110`.
Its existing [factory-chain evidence](native_lua_class_factory_survey.md) seals
body SHA-256
`a138a00ca47281aa3b4fb0db11a3aa5e875616a57b3684f7598e4b0517b900e3`
and CFG SHA-256
`c1212e08e59965211c3691fc52551f88f3441ba801bcfa7fe599afcb775dd55b`.
Independent read-only reconstruction rechecked the exact installed PE body on
September 12. The facts below are integration requirements, not a joined native
callback execution receipt or a source-level inheritance claim.

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

## Work required before claiming composition

1. Compose helper entries, return addresses, caller registers and preserved ancestor
   stack storage at these actual frames. The marker and table helpers now accept
   checked caller mappings and have focused native cases at these continuations;
   a single continuous callback execution is still required.
2. Parameterize the class record address and contents. Existing class fixtures
   use a fixed record at 0x14000200; this caller supplies F-16 with first word
   zero. Its object pages must also retain the registry-reference fields and
   final word-zero data.
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
