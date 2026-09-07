# Bounded feature-zero scalar copy

The copy helper's scalar and REP DWORD paths now have a bounded contract for
lengths 32 through 2048. Both feature words at RVAs `0x00493f30` and
`0x004b6e48` are fixed to zero, and entry DF must be clear. These explicit
settings exclude SIMD and the separate forward REP byte path.

The model covers destination-alignment byte prefixes, forward and backward
REP MOVSD transfers, both four-entry tail tables and the short scalar
fallbacks. Lengths 32 through 34 can fall below 32 after alignment and rejoin
the previously established short loops. Backward REP uses STD and CLD;
exit DF is zero. Source snapshots and nonwrapping protected storage are
required, and overlapping destinations receive the original source bytes.

Return is cdecl with EAX=destination, ECX=zero, original nonvolatile registers
restored and ESP advanced by four. EDX and final flags depend on the chosen
path. Forward REP leaves flags from masking the remainder; backward REP leaves
flags from subtracting four from the adjusted destination endpoint. Those
backward flags are not a uniform zero-count result. Short fallbacks retain
their scalar-loop register and flag relations.

## Evidence and limits

Exact witnesses retain the full 1,330-byte, 404-site discontiguous body and
identify the executed scalar ranges: 498 bytes and 176 sites. The semantic
model checks 3,168 cases. The Unicorn 2.1.4 replay checks 1,620 cases, with
1,080 forward and 540 backward, all 176 sites and two negative controls.
REP iterations, feature-word reads and native table reads execute and are
checked as ordered memory events. Complete stack and payload bytes, table
and feature storage, general registers, defined arithmetic flags and DF
match independent snapshot and access oracles.

Independent semantic and replay reviews passed. All 33 focused tests passed,
including exact-executable CLI rebuilds. Feature-enabled paths, larger lengths,
entry DF set and whole-program equivalence remain outside this checkpoint.
No API or game code runs and no accounting promotion is claimed.

## Reproduction

`scripts/itb_native_scalar_copy_semantics.py` accepts `--program-facts` and
`--small-copy-semantics`; its conformance counterpart accepts `--semantics`.
Both expose `build`, `verify` and `verify-structure`. Exact commands require
`--executable`; verification requires `--evidence`.
Published prefix: `windows_build_13725832_31fe35265598_`.

- `native_scalar_copy_semantics.json`: canonical
  `f15d777d0015508025011c796882044f5f9f79f3eeb09fd9fd714bb2ae8fd428`;
  raw `0a3e6fb3d9f49f9142e27080a437d001b70d978477e249a9399c7f00cb538181`.
- `native_scalar_copy_conformance.json`: canonical
  `60ddfcb642d675f73c4b8991270400802f08b6d8f78faa9da55f80279d6171a9`;
  raw `621ae5fc606fe6316bffa78152c601193921a3778cecfbe640ab24d524077c0d`.
