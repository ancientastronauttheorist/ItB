# Vector growth capacity decision

The exact Windows helper at RVA `0x002eb620` now has a strict 32-bit
specification and a bounded executable replay. Its full static extent is
94 bytes/40 instruction sites. The proof covers the 33 decision sites and
stops before the resize call at `0x002eb669` or cleanup at `0x002eb66f`.
Allocation, relocation and return cleanup remain separate work.

ECX supplies a stable three-word record: begin, end and capacity at offsets
0, 4 and 8. Object and stack storage must be mapped and disjoint. The first
test takes the no-growth path exactly when the wrapped unsigned byte
difference `capacity - end` is at least eight. Negative signed differences
therefore usually take that same path. Synthetic machine words are not
automatically valid C++ vector objects.

For ordered, nonwrapping fields whose element differences are multiples of
eight and total byte span is below 2^31, this reduces to a familiar relation:
retain spare capacity; when full, request the larger of `size + 1` and
`capacity + floor(capacity / 2)`, in elements. Larger byte spans require the
separate machine relation because the native shifts are signed arithmetic
shifts, not unsigned division.

The strict machine relation computes size and capacity as unsigned words
representing signed division by eight. It adds one to size with wrapping,
forms a guarded geometric candidate, then takes the unsigned maximum.
The guard selects the geometric candidate for nonnegative signed capacity
differences and zero for negative ones. EAX still retains the computed sum
even when the candidate is discarded; EBX retains the wrapped guard bound.

## Unreachable failure branch

The apparent size-limit failure requires the shifted size word to equal
`0x1fffffff`. Arithmetic right shift by three can only produce unsigned
words in `[0,0x0fffffff]` or `[0xf0000000,0xffffffff]`. The required value
is outside that image. The failure block at `0x002eb674` is therefore
unreachable from this entry under the stated stable-memory execution domain.
This is an arithmetic argument, not an inference from missing test coverage.

## State and validation

Let S be entry ESP. At the no-growth frontier, ESP is S-8 and the two stack
writes preserve entry ESI and EDI. At the resize frontier, ESP is S-16;
additional words preserve entry EBX and pass the computed element request.
The caller's return and argument words remain unchanged. Both frontiers
retain the object pointer in ECX and ESI. All general registers, ordered
operand accesses and final comparison flags are checked.

The graph receipt covers 16,528 cases: 4,912 resize frontiers, 11,616
no-growth frontiers, and no failure frontiers. Five semantic mutations are
rejected. A separate Unicorn 2.1.4 experiment runs 3,168 exact-byte cases,
split equally between the two reachable frontiers, across all 16 stack
alignments. Its independent mathematical oracle compares all general
registers, CF/PF/AF/ZF/SF/OF, the entire mapped stack and metadata, and the
ordered reads/writes. A changed machine field fails the oracle. No CALL,
cleanup, allocator, or game process executes in that experiment.

The 75 focused semantic and conformance tests passed, including deterministic
subprocess CLI builds. Independent semantic review passed. No atlas promotion or
replacement of the existing append growth summary follows yet.

## Reproduction

`scripts/itb_native_lua_vector_growth_semantics.py` provides `build`,
`verify` and `verify-structure`. Its pinned inputs are `--chain`,
`--program-facts` and `--append-semantics`. Build and exact verification take
`--executable`; verification also takes `--evidence`.

`scripts/itb_native_lua_vector_growth_conformance.py` provides the same
commands with `--semantics` as its evidence input, and requires Unicorn
2.1.4 for exact replay. Set `ITB_EXACT_EXE` and the private Unicorn
`PYTHONPATH` when running the focused tests.

The published files use the prefix
`windows_build_13725832_31fe35265598_native_lua_vector_growth_` in
`data/observatory/programs/`:

| Receipt | Canonical SHA256 | Raw UTF-8/LF SHA256 |
| --- | --- | --- |
| `semantics.json` | `6e442065281f9d7f1853dbb2d2dd91b3d5645cae16a5497db772b7a66f28ec69` | `b19f03fe991b0257edf73580865efacb32502711ce6955a06bc6f0b0f37fc73a` |
| `conformance.json` | `e183ac0be6298ac190f4b4d83e0201366be59156e4f40ec04c7dd3f738105740` | `e93fc6fe85be4fc848d3dbd8c2d0d53ab9e25fa137dd35d36fb703450c84eac9` |

Next: allocation-request decision at `0x0008a920`, reached through the resize
child `0x002eb680`. Successful allocation, alignment, copying, freeing and
the enclosing owner's tree insertion remain open.
