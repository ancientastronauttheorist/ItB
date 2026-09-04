# Assertion descendant fill conformance

This is finite emulation evidence for the 346-byte function at Windows RVA
`0x00370960`, executable SHA-256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
The exact body and instruction witnesses join the immutable leaf-callee
receipt. The `_memset` analysis label is not used as proof.

The sealed run contains **14,620 conforming cases** (14,616 ordinary vectors
and four null-destination zero-length cases), plus one expected direction-flag
rejection. Its traces cover all 89 sealed instruction nodes and 102 CFG edges;
this does not establish exhaustive paths or inputs.

Artifact: `data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_fill_conformance.json`.
Raw SHA-256: `2b252e9dfa988551c8a110d90abe539f20c00bbc62bea27c34f6441d6d67bcbf`.
Canonical SHA-256: `6f4bba8750713184f5de2bf119b36605078e4386e05712a2f686b6e744801246`.

## Independent specification

For a valid finite destination interval, the independently authored `fill_spec`
replaces each byte with the low eight bits of the value argument and preserves
all other bytes. It does not reproduce the native function's branch algorithm.
The emulator also requires the destination in EAX on return, entry ESP plus
four at the return sentinel, unchanged EBX/ESI/EDI/EBP and input frame, and a
write union equal to the destination interval. Repeated and overlapping SIMD
writes are allowed, but every individual write must stay inside that interval.

Data-read hooks admit only the 16-byte argument/return frame and the two
four-byte dispatch inputs. Execution hooks restrict instruction execution to
the exact body until the return sentinel. Full-buffer comparison against a
nonuniform initial buffer additionally checks canaries; write hooks catch
out-of-range writes even if their values would leave canaries unchanged.

## Finite domain

The matrix uses all 16 destination residues modulo 16; lengths 0 through 40;
values around 64, 96, 128, 256, 384, 512, 1024 and 4096; and alignment-dependent
transitions around `144 - alignment` and `400 - alignment`. Each transition
uses its preceding, exact and following length. All four combinations of bit
one in the two dispatch globals are exercised. Additional vectors cover low
bytes 1, 127, 128 and 255, a value of 256, and unrelated dispatch-global bits.
The matrix and exact vector hash are retained in the normalized receipt.

Four additional zero-length cases use an unmapped null destination. A separate
REP-enabled, direction-flag-set case must be rejected for a write outside the
forward destination interval. Positive vectors require DF clear. This negative
control demonstrates why that precondition matters; it is not a conforming
fill result.

Execution occurs in Unicorn 2.1.4, native version tuple `(2, 1, 33621247)`, with
explicit model `UC_CPU_X86_HASWELL` (19), 32-bit mode and flat segments. The
model is an emulator configuration, not evidence that the installed game uses
those dispatch settings or that host hardware behavior has been validated.
Only the exact function bytes are loaded from the owner's executable into the
isolated emulator. No game process is attached, executed or modified.

## Limits

The evidence covers the declared finite vectors, not all paths or inputs.
Instruction/CFG coverage excludes repeated same-address REP events and does
not prove micro-iteration coverage. Oversized signed lengths, pointer wrapping,
nonempty inaccessible buffers, overlaps with code/stack/globals, non-flat
segments, CPU feature availability, faults, concurrency, timing, flags and
volatile-register results are outside the claim. CRT identity, global ownership,
real-game execution and accounting promotions remain open.

The parent's two call sites stage lengths 80 and 716. Those exact lengths are
not members of this boundary-focused matrix. Connecting the caller to the fill
contract still requires argument-stack and destination-region proofs plus
caller-specific conformance vectors; this receipt does not claim that join.

PE-free verification checks the sealed normalized receipt and regenerates the
finite vector identities. Exact verification reruns the body in the emulator;
it canonical-pins the source receipts without rerunning their earlier
whole-atlas analyses. Existing receipts remain immutable.

## Reproduction

Install the optional emulator in an isolated local directory:

```powershell
python -m pip install --target .local_decompile/fill_runtime unicorn==2.1.4
$env:PYTHONPATH = '.local_decompile/fill_runtime'
python -X utf8 scripts/itb_native_assertion_helper_fill_conformance.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --leaves data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_leaf_callees.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_fill_conformance.json
```

For `build`, use `--output` instead of `--evidence`. For `verify-structure`,
omit `--executable`; Unicorn is not required. No proprietary bytes or emulator
binaries are published with the receipt.

The gated exact pytest check launches the CLI in a child process. On this
Windows setup, running Unicorn CPU-model controls inside pytest's fault handler
produced repeated access-violation diagnostics while the process continued.
The separate CLI process avoids that interaction; the test requires a zero
exit status, empty stderr and a verified JSON result. A crash, timeout or
missing emulator fails the enabled check rather than becoming a gated skip.
