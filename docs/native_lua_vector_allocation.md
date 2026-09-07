# Vector allocation request decision

The helper at RVA `0x0008a920` has a 91-byte/34-node static body. Its bounded
decision specification covers 19 nodes, including the complete zero-count
return, and stops before either allocator call or either failure call.
The caller edge from resize helper `0x002eb680` is verified statically; this
does not establish execution or effects of that resize helper.

The input is a strict unsigned 32-bit element count, with eight bytes per
element. Its complete request partition is:

| Count | Decision | Byte request |
| --- | --- | --- |
| 0 | Return zero | None |
| 1 through 511 | Small request | `8 * count` |
| 512 through `0x1ffffffb` | Large request | `8 * count + 35` |
| `0x1ffffffc` through `0x1fffffff` | Padding overflow failure | None |
| Above `0x1fffffff` | Size failure | None |

The two successful request frontiers target `0x003574db`; their CALL
instructions are not executed. The two failure frontiers target
`0x003435bc`, also unexecuted. Both allocation requests are byte counts,
not element counts. For the four padding-overflow inputs, the wrapped
padded words are respectively 3, 11, 19 and 27, but none is passed as an
allocation request.

Let S be entry ESP. Nonzero paths save EBP at S-4 and set EBP to S-4.
Request paths additionally push their byte count at S-8; failure paths
stop with ESP at S-4. The zero path restores EBP, returns through the
caller return word and cleans the count argument, ending with ESP=S+8
and EAX=ECX=0. Other general registers are preserved on this call-free
zero path. It does not invoke an allocator.

## Evidence and limits

The graph receipt checks 19,744 cases: 32 zero returns, 16,352 small
requests, 2,496 large requests, 736 size failures and 128 padding failures.
Six semantic mutations are rejected. The independent Unicorn 2.1.4 receipt
checks 672 exact-byte cases across all 16 stack alignments and two register
and memory seeds: 32 zero returns, 160 small requests, 256 large requests,
96 size failures and 128 padding failures.

Both experiments check complete general-register output, ordered stack
accesses and protected frame words. The exact replay checks the entire
mapped stack. Nonzero paths expose final CMP flags. The zero path ends
with XOR flags: CF, PF, ZF, SF and OF are checked; AF is undefined and
deliberately omitted. A changed input that crosses the 511/512 boundary
fails the independent replay oracle.

All 28 focused tests passed, including exact-executable and Unicorn
subprocess CLI rebuilds. Independent semantic and replay reviews passed.
No allocator, failure function, post-allocation alignment tail, game process
or complete resize operation executes in these receipts. They do not
promote the whole-program accounting ledger.

## Receipts and reproduction

`scripts/itb_native_lua_vector_allocation_semantics.py` takes `--chain`,
`--program-facts` and `--growth-semantics`; its `build` and `verify`
commands also take `--executable`. Both verification commands take
`--evidence`. The corresponding `itb_native_lua_vector_allocation_conformance.py`
uses `--semantics` and requires Unicorn 2.1.4 for exact replay.

Published filenames share
`windows_build_13725832_31fe35265598_native_lua_vector_allocation_` in
`data/observatory/programs/`:

| Receipt | Canonical SHA256 | Raw UTF-8/LF SHA256 |
| --- | --- | --- |
| `semantics.json` | `9081f912a66487224a7924c126fad24a38d8cbdb4f37cb69e3e45902074f805c` | `626d37646d599f31d4ade3c348ba93294bcec01a5934b9da67eae80bc0c2665f` |
| `conformance.json` | `e76e77dec37818df255c4cde2c1fd1142628dc63be4b8bfbb02e79860b4b4cca` | `d53f56efab85d6fa4b1599d9addcf463a5d08a3c7a7a579ec0ab2a7d9ae60872` |

Next: specify the two return tails under explicit post-call state premises,
including the large-request alignment metadata write. Actual allocation
success and usable storage remain separate premises until their machinery
is recovered and verified.
