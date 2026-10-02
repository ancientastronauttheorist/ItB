# Selected AddMove and AddCharge binding

The exact Windows build statically binds the complete names `AddMove` and
`AddCharge` to native methods at RVAs `0x00257340` and `0x002576f0`. The
initializer argument recipes, their two builders and the selected parent
bodies are executable-rebuilt evidence. Runtime Lua publication, class
namespace, ownership, child behavior and actual pawn movement remain open.

## Name and builder joins

The initializer is decoded from its actual entry `0x00279880`, covering
32,310 bytes and9,348 instructions. Each selected name has one complete
nine-instruction recipe: store the method address into a frame slot, push
that slot's address and the complete NUL-terminated name, then call its
builder. No intervening instruction can overwrite the method slot.
`AddMoveBonus` is a separately checked complete name.

Each147-byte builder allocates20 bytes and selects record fields at offsets
0/4/8/12: vtable, zero next link, name address and dereferenced method slot.
No selected store initializes offset16. The incoming registration object
provides the owner through its DWORD at offset4; the owner list is at offset64.
The selected source writes either the empty list root or the last node's next
link, returns the incoming object in EAX and consumes20 caller bytes.
These are source relations, with allocator and valid-list behavior excluded.

## Parent relations and graphs

AddMove reads a by-value path triple and computes `(end-begin) SAR3`, then
uses an unsigned comparison against1 to select record work. The skip path
assigns BL0, the record path assigns BL1 and the suffix copies BL into AL.
No return-value preservation across opaque child calls is inferred. A
selected MOVSS copies the fourth caller word to local record offsetC8.
Nonzero begin supplies the path-free guard with stride8. The method consumes
16 caller bytes. Record construction, copying, appending and destruction are
named direct-call frontiers rather than established child semantics.

AddCharge calls AddMove, tests the returned AL and, if nonzero, reads the
receiver's end word and stores DWORD2 at `end-92`. Relating this to a final
effect record requires independently establishing the append layout.

The four complete selected bodies have220 instruction nodes and226 syntactic
CFG edges: each builder51/53, AddMove72/73 and AddCharge46/47. Calls have
possible fallthrough in this source graph; runtime return, SEH and unwind
behavior are not guaranteed. All selected direct-call edges agree with the
pinned program atlas.

## Receipt and reproduction

The normalized receipt is
`windows_build_13725832_31fe35265598_native_movement_effect_binding.json`:

- Canonical SHA256: `54c060913d61f6bb5e4c1f2586f0d5186ea73ad6c058dd48b1cc056e64a410b9`.
- File SHA256: `8dcab678554d5baa3d62ed79ddf51f861cdd13ea3608a08eb5ef670e6bafd86b`.
- 92,129 bytes and one exact program-facts pin; zero accounting promotions.

Independent source/CLI and final receipt review are GO. The independent
test packet handwrites selected instruction encodings, complete branch/call
graphs and field/argument relations rather than taking them from a rebuilt
receipt. It checks typed source/receipt/schema mutations, complete literals,
detached outputs, selected executable mutations and exact CLI encoding.
All130 focused tests pass without skips in207.49seconds, including exact
source rebuild and build/verify/verify-structure CLI commands. This remains
static binding evidence; native movement execution is a separate frontier.

Use `scripts/itb_native_movement_effect_binding.py` with `--program-facts`.
`build` and `verify` require the privately supplied exact `--executable`;
`verify` and `verify-structure` require `--evidence`. Source extraction and
tests run serially in isolated subprocesses. Only normalized hashes, selected
relations and graph metadata are published, never opcode bytes or raw source.
The next bounded native frontier is AddMove's null/empty-owned/one-point path.
