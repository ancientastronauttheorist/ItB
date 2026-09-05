# Assertion caller fill composition

The exact prefix of Windows function RVA `0x00379d28` now joins its two fill
calls to the independently specified `0x00370960` body. The proof stops before
RVA `0x00379d79`, after shared argument cleanup and before the next pointer
store. This is 81 caller bytes and 25 caller instructions, not the whole
315-byte function.

The sealed run passes **256 prefix cases and 512 fill observations**, with
128 executions of the optional eight-byte helper. All 25 prefix instruction
nodes are observed. Across the prefix and both callees, 111 nodes are observed;
this is not a claim of full fill-body or path coverage. One DF-set negative
control rejects the second fill for an out-of-region write.

Artifact: `data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_caller_fill.json`.
Raw SHA-256: `4206855ecf4c727e3a85ab9bb8fa5c2f37ecb1c51b2f7eb1f696c049d9754d48`.
Canonical SHA-256: `b89d1873e56c4afb27c96229c05a1a0516732a5bdc3d2151173baeb5d4a5b653`.

## Frame arithmetic

Let `F` be the established EBP, equal to entry ESP minus four. Selected
prologue and argument-setup instruction grammars are checked against exact
pinned instruction witnesses. The following intervals use half-open bounds:

| Region | Interval relative to F | Bytes |
|---|---|---:|
| Reserved locals | `[-0x328, 0)` | 808 |
| Untouched locals at this boundary | `[-0x328, -0x320)` | 8 |
| First zero region | `[-0x320, -0x2d0)` | 80 |
| Second zero region | `[-0x2d0, -4)` | 716 |
| Protected XOR slot | `[-4, 0)` | 4 |
| Saved EDI | `[-0x32c, -0x328)` | 4 |
| Saved EBP | `[0, 4)` | 4 |

The fill regions are adjacent, disjoint, inside the local allocation, and share
`F mod 16` alignment. They cover 796 bytes and stop before the protected slot.
The outgoing argument and return stack extends below the local allocation;
the lowest checked offset is `F - 0x348`.

At call `0x00379d58`, fill-entry ESP is `F - 0x33c`; at call `0x00379d6b`, it
is `F - 0x348`. Each entry frame contains the exact return address, destination,
zero value and length at offsets 0, 4, 8 and 12. The arguments are retained
across the two calls, then removed together by the 24-byte cleanup. At the
exclusive stop, EBP is F, ESP is `F - 0x32c`, and EAX is `F - 0x320`.

## Finite composition checks

The matrix varies all 16 frame alignments, all four combinations of dispatch
bit one, selectors zero and `0xffffffff`, and two protected-slot seed values.
The slot contains the selected seed XOR F. The optional helper has an
eight-byte body but a **four-byte** zero effect at global RVA `0x004b6e58`;
its argument and return stack is cleaned before either fill. The two selector
values exercise both prefix branches without proving every selector input.

Each fill is checked separately against the independent full-stack byte-fill
oracle. Hooks enforce that fill's own write interval and exact write union,
including when an out-of-region write would touch already-zero memory. The
return continuation, destination result, stack increment and preserved
registers are checked at each call boundary. Parent writes are checked against
explicit expected addresses, widths and values; a final whole-stack oracle
protects the untouched locals, saved registers, incoming frame and XOR slot.
Data-read hooks are limited by the executing component. A full global-page
oracle permits only the optional four-byte zero effect.

The 81-byte prefix and exact eight-byte and 346-byte callees execute together
in an isolated Unicorn instance for each vector. Emulator pins remain
Unicorn 2.1.4, native core `(2, 1, 33621247)`, and explicit
`UC_CPU_X86_HASWELL` model 19 in 32-bit mode with flat segments. The game
process and installation are not modified.

## Scope and reproduction

This combines selected setup grammar, static interval arithmetic and finite
exact-prefix emulation. Branch, protected-slot and call effects are observed
on the declared matrix, not universally proved. DF clear, mapped nonwrapping
stack memory and the pinned emulator configuration are premises. Whole-caller
return, later stores, context/reporting identity, real CPU execution, faults,
concurrency, global ownership and accounting promotions remain unproved.

The earlier boundary and 14,620-case fill receipts remain immutable. They are
canonical-pinned, while the current PE and body instruction witnesses are
rechecked; their whole original analyses are not rerun. PE-free verification
recognizes the sealed receipt and recomputes layout and vector identities.

Use the optional emulator installation described in `docs/native_fill_conformance.md`:

```powershell
$env:PYTHONPATH = '.local_decompile/fill_runtime'
python -X utf8 scripts/itb_native_assertion_helper_caller_fill.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --pair data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_descendant_pair.json `
  --leaves data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_leaf_callees.json `
  --conformance data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_fill_conformance.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_caller_fill.json
```

For `build`, replace `--evidence` with `--output`. For `verify-structure`, omit
`--executable`; Unicorn is not required. The gated exact test runs the CLI in a
child process to avoid the Windows pytest/Unicorn fault-handler interaction.
