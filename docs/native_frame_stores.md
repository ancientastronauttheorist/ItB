# Assertion frame-store slice

The exact Windows slice `[0x00379d79, 0x00379e20)` populates fields after the
two cleared regions. It covers **167 bytes and 30 instructions**, stopping
before the first import call. The immutable caller-fill receipt supplies the
boundary EAX/EBP/ESP and zero-region premises; arbitrary volatile register and
flag samples here are not claimed reachable from that earlier prefix.

All **256 synthetic boundary states** pass the independent overlay and ordered
memory-event checks. Each case has 22 frame writes (16 dword and six word),
one temporary dword write, and six reads. The frame writes cover 76 distinct
bytes; the temporary covers four more. These are bytes written, not necessarily
bytes whose values changed. Two deliberately incorrect oracles are rejected:
a widened segment-word store and an ECX field incorrectly sourced from EDX.

Artifact: `data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_frame_stores.json`.
Raw SHA-256: `09515f803d5b7bf9e6534a62540fbfb740f89d9b32216f2d6508e9ae1a54aef0`.
Canonical SHA-256: `69afa7ae52de9fe086d15f92350394518db88be433f7b9b3f5607c1a0a36d0b1`.

## Declarative transfer map

Let F denote EBP at slice entry. EAX starts at `F-800`, ESP at `F-812`, and
`[F-800,F-4)` is zero under the entry premise. The table lists byte offsets
from F, not structure/type identifications:

| Offset | Width | Value source |
|---:|---:|---|
| -808 | 4 | F-800 |
| -804 | 4 | F-720 |
| -544 | 4 | F-720, computed inside the slice |
| -548 | 4 | Boundary ECX |
| -552 | 4 | Boundary EDX |
| -556 | 4 | Boundary EBX |
| -560 | 4 | Boundary ESI |
| -564 | 4 | Boundary EDI |
| -520 | 2 | SS selector |
| -532 | 2 | CS selector |
| -568 | 2 | DS selector |
| -572 | 2 | ES selector |
| -576 | 2 | FS selector |
| -580 | 2 | GS selector |
| -528 | 4 | Pushed flags image |
| -536 | 4 | Incoming word at F+4 |
| -524 | 4 | F+4 |
| -720 | 4 | Constant 65537, purpose unclassified |
| -540 | 4 | Incoming saved-EBP word at F |
| -800 | 4 | Incoming word at F+12 |
| -796 | 4 | Incoming word at F+16 |
| -788 | 4 | Incoming word at F+4 |

PUSHFD additionally writes `[F-816,F-812)`. POP copies that value into the
frame but leaves the temporary bytes behind, restoring ESP to F-812. The
independent whole-stack oracle includes that stale temporary. The incoming
F+4 word is read twice; final EAX equals that word. Other general registers,
EBP, ESP and sampled flags retain their boundary values.

The six segment stores are two bytes wide. Their adjacent upper halfwords
remain zero under the zero-region premise. The map therefore does not widen
them to four-byte fields, even though zero-valued runtime selectors could hide
such an error in a final-buffer comparison alone. The ordered event oracle
rejects that widening independently of the stored values.

## Evidence and limits

A generic symbolic MOV/LEA/PUSHFD/POP grammar extracts the normalized stores
and reads from exact instruction witnesses. Its results must match the
independently authored overlay table. Concrete replay then checks every
instruction in sequence, exact ordered read/write addresses and widths/values,
the complete final stack, final EAX and preserved boundary registers. Code and
execution stop at the exclusive import boundary.

The finite matrix uses 16 frame alignments, two distinct general-register
sets, two incoming-word sets and four safe flag images. Runtime selectors are
zero in the flat-segment emulator. The overlay specification can represent
nonzero selector words, but nonzero-selector runtime behavior is not proved.
The flags input is the pushed image of current boundary flags, not original
caller-entry flags; RF, VM and other unsampled flag images are outside scope.

The field at F-544 receives the pointer computed by this slice, not original
caller-entry EAX. ECX/EDX and flags may have been affected by the preceding
fills. This receipt samples those boundary values independently; it does not
establish their full-prefix reachability or identify an original CPU context.
Structure/ABI names, later import behavior, whole-function return, native game
execution, faults, concurrency, ownership and accounting promotions remain open.

The additive receipt in `docs/native_import_handoff.md` now carries the actual
prefix state into this slice on the caller's 256-case matrix. It supplies
independent volatile-value and last-writer checks, without changing the
arbitrary-boundary domain or identity of this store-only receipt.

Unicorn is pinned to 2.1.4, native core `(2, 1, 33621247)`, explicit
`UC_CPU_X86_HASWELL` model 19, 32-bit flat-segment mode. Existing source
receipts remain immutable and canonical-pinned. Exact verification rechecks
the executable and complete owner instruction witnesses, then reruns this
matrix; earlier whole-atlas scans and emulation matrices are not rerun.

## Reproduction

Use the optional installation in `docs/native_fill_conformance.md`:

```powershell
$env:PYTHONPATH = '.local_decompile/fill_runtime'
python -X utf8 scripts/itb_native_assertion_helper_frame_stores.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --pair data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_descendant_pair.json `
  --caller data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_caller_fill.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_frame_stores.json
```

For `build`, use `--output` instead of `--evidence`. For `verify-structure`,
omit `--executable`; Unicorn is unnecessary. Exact pytest replay uses a CLI
child process to isolate the Windows pytest/Unicorn fault-handler interaction.
