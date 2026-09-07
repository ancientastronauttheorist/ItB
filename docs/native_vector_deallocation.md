# Vector deallocation guards

The 91-byte, 29-site helper at `0x00007800` validates an element count,
stride and pointer before transferring to free. Its 25 guarded sites now
have an independent integer model and exact x86 replay. The free CALL and
three return-tail sites are outside this checkpoint.

For nonzero stride, unsigned division computes floor(UINT32_MAX / stride)
and its remainder. A count above that quotient takes the failure jump;
otherwise the count-times-stride product cannot overflow. Products below
4096 pass the supplied pointer unchanged, including zero. Larger products
require a 32-byte-aligned pointer and read its preceding DWORD. That raw
word must be strictly below the payload pointer, at a distance from four
through 35 bytes inclusive. A valid large case passes the raw word to free.
These guards do not establish allocation provenance or ownership.

Zero stride stops before DIV and its operand read, even for zero count.
No divide fault executes. Guard failures stop at the external jump target
`0x00379f02`; valid guards stop before CALL `0x00007851`. The isolated replay
maps an excluded synthetic stop byte at the failure destination solely to
bound translation, and its hook stops before that byte executes.

## Allocation inverse and evidence

The resize caller's exact 101-byte, 46-site witness pushes stride eight.
Under the separately established positive, nonwrapping allocation-block
premise, every large allocation alignment offset passes these guards and
recovers the original block pointer from metadata. This inverse is conditional
on valid storage; pointer arithmetic alone does not prove a live allocation.

The semantic receipt checks 15,680 cases: 1,280 division frontiers, 7,744 free
frontiers and 6,656 guard failures. It also checks 288 allocation inverses,
five semantic mutations and protected-frame alias rejection.
The Unicorn 2.1.4 receipt checks 2,832 cases across all 25 guarded sites:
32 division frontiers, 1,792 free frontiers and 1,008 failures, plus two
negative controls. All 16 stack alignments are sampled. Full general registers,
defined arithmetic flags, stack and metadata pages, and ordered native memory
accesses match an independent oracle. The alignment TEST uses AL, so its flag
semantics are eight-bit; undefined AF is not claimed.

All 65 focused tests passed, including both exact-executable CLI rebuilds.
Independent semantic and replay reviews passed. No free operation, failure
callee instruction, actual divide fault or whole-program accounting promotion
is claimed.

## Reproduction

`scripts/itb_native_vector_deallocation_semantics.py` accepts `--program-facts`,
`--allocation-semantics` and `--return-semantics`; its conformance counterpart
accepts `--semantics`. Both expose `build`, `verify` and `verify-structure`.
Exact commands require `--executable`, and verification requires `--evidence`.
Published prefix: `windows_build_13725832_31fe35265598_`.

- `native_vector_deallocation_semantics.json`: canonical
  `7db0ff16946971f721c3d8246af544a5d009095004a63453285f72d4b05de351`;
  raw `608f424e44bb001bb03497eaa32b374c72cc732e812439cb34ca8978c6336ab0`.
- `native_vector_deallocation_conformance.json`: canonical
  `d54d38e2d758d2166f850346b3850cb608cda13aabb317a688edae513499954a`;
  raw `cb1d6b43f6be249718d0f22ba593a38288351019ac0e19c7bcd74b2dae060129`.

Next: the free wrapper's null, success and error paths, followed by a joined
resize contract with explicit copy and storage assumptions.
