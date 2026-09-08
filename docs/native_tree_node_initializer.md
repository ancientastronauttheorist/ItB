# Conditional tree node initializer

The initializer at RVA `0x0007d060` has 51 bytes and 25 instructions. It
pushes request 24 and calls the pinned retry target `0x003574db`. This
checkpoint supplies one opaque normal cdecl return with EAX=P, sampled
ECX/EDX/arithmetic flags, and preservation of all modeled storage,
nonvolatile registers and DF. Native CALL's continuation write is distinct
from the opaque summary's continuation read. No retry instruction executes.
The static incoming factory call `0x0007cd93` is independently verified;
factory behavior is not composed here.

For modular addresses P, P+4 and P+8, the initializer skips only an address
equal to zero. Otherwise it rereads the source head DWORD and then stores
that value at the field address. These reads cannot be collapsed when source
and destination partially alias. For example, with head `0x11223344` and
P one byte below the source, the three stored values are `0x11223344`,
`0x11112233` and `0x33112233`.

Every actual DWORD must be mapped, must not cross the 32-bit address
boundary, and must be separate from protected frame and code. Partial
source/destination byte aliases are permitted and modeled in order. P=0
still writes addresses four and eight. P=`0xfffffff8` and `0xfffffffc`
skip individual modular zero fields under explicitly mapped high/low-page
premises. These synthetic returned-pointer cases are not inferred reachable
allocator results and do not establish harmless null behavior.

For a nonnull nonwrapping fresh 24-byte block separate from source and frame,
the ordinary corollary is simpler: offsets 0, 4 and 8 equal the original head,
and bytes 12–23 remain unchanged. EAX returns P and ECX is modular P+8.
EDX is the first head read when P is nonzero, otherwise the supplied opaque
EDX. Saved registers restore; cdecl return advances entry ESP by four.
Final TEST of P+8 defines CF/OF zero and SF/ZF/PF from its result; AF is
undefined. DF preserves its entry value.

## Evidence and reproduction

The semantic graph checks 1,776 cases; exact Unicorn 2.1.4 replay checks
3,552 cases. Both cover all 25 sites and 51 bytes, with independent review
GO. Native replay includes all 16 frame alignments, both DF values, 37
pointer fixtures and three head values. General registers, defined flags,
ordered native/opaque events and complete mapped pages including padding
are checked. Cached-head and returned-pointer replay mutations are rejected;
the semantic controls also reject a changed null guard.

`scripts/itb_native_tree_node_initializer_semantics.py` takes
`--program-facts` and `--retry-semantics`; the conformance script takes
`--semantics`. Both expose `build`, `verify` and `verify-structure`, using
deterministic UTF-8/LF JSON through binary stdout. Exact commands require
`--executable`; verification requires `--evidence`.

`tests/test_itb_native_tree_node_initializer.py` checks fresh-block bytes,
literal alias-feedback values, modular zero guards, malformed premises,
receipt integrity and gated exact CLI rebuilds. All 43 tests passed, including
both exact CLI rebuilds. Set `ITB_EXACT_EXE` and
the private `.local_decompile/fill_runtime` on `PYTHONPATH` for exact checks.
Actual allocation, invalid/unmapped storage, factory composition and global
accounting promotion remain excluded.

Published prefix: `windows_build_13725832_31fe35265598_`.

- `native_tree_node_initializer_semantics.json`: canonical
  `445d6993772da858de7bfb28b0852ceb5201922cfe024c847cfd6c1f36d45a85`;
  raw `b70068e94024626aa1255edc1980be27cc484ee8680772dc9ed7ac8a63bfb03b`.
- `native_tree_node_initializer_conformance.json`: canonical
  `da2ed4fde20e1df51447258edbcbd11e394442669554af9832881462c708bcc0`;
  raw `0d948405547c6ce9e62c53a7047f3f691d6d171c1e3746ab32952754cb92f8a9`.
