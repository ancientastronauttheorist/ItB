# Assertion import handoff composition

This follow-up joins the previously verified caller prefix and frame-store
slice of Windows owner RVA `0x00379d28`. Its exclusive stop is `0x00379e20`,
before the first imported call. The combined caller interval contains 248
bytes and 55 instructions; the optional small helper and both calls into the
fill body execute as part of the prefix.

The sealed run passes **256 composed cases**, with 512 fill observations and
128 optional-helper executions. It observes all 55 caller-prefix nodes and
141 nodes across caller and callees. Each store phase checks 23 writes and
six reads. A deliberately altered boundary ECX is rejected before its value
can be accepted as an overlay input.

Artifact: `data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_import_handoff.json`.
Raw SHA-256: `c8262ccee8149477fc52f49e5a5fdc22cf4b7d6898f1eea26a763ab169c7af39`.
Canonical SHA-256: `21ed5942d039ec0e16c94f40447f0e15bebea6d74298a1af448eb93f55ce7712`.

The new question is whether the stored volatile values actually arise from
that prefix. The earlier store receipt intentionally supplied arbitrary
boundary samples. Here, the prefix and stores share one emulator instance,
with no reseeding of architectural state between them. Execution pauses at
`0x00379d79` so the existing prefix oracle can check the complete stack and
global pages; hooks then change and execution resumes from the same state.
This uses two emulator invocations, not a single invocation.

## Independently derived boundary values

Let F be established EBP. The finite matrix fixes F to `0x02002000 + a`, for
alignment a from zero through fifteen. It retains the caller receipt's four
dispatch-word combinations, two selector values and two cookie seeds.

The last fill determines ECX and EDX. The final caller stack cleanup then
determines arithmetic flags. These are values at the store boundary, not a
capture of the original caller-entry CPU registers.

| Boundary value | Expected source on this matrix |
|---|---|
| EAX | F-800, from caller pointer setup |
| ECX, REP path | Zero |
| ECX, scalar path | Zero |
| ECX, SIMD path | `(28 + a) mod 32` |
| EDX | Entry EDI, fixed here to `0x3456789a` |
| EFLAGS | Arithmetic flags of adding 24 to F-836, with reserved bit one set |
| EBP / ESP | F / F-812 |

The REP dispatch has priority. Only the combination REP word zero and SIMD
word two selects the SIMD expression. The ECX last-write witnesses are
`0x0037099c` for REP, `0x00370aa8` for scalar and `0x00370a41` for SIMD.
EDX's witness is `0x00370969`; the final arithmetic-flags writer is
`0x00379d76`.

At these synthetic stack addresses the final addition clears carry, overflow,
sign and zero flags. Auxiliary carry is set for alignments 0–3 and 12–15;
parity follows the low byte of F-812. The expected EFLAGS values by alignment
are `22, 18, 18, 22, 6, 2, 2, 6, 2, 6, 6, 2, 18, 22, 22, 18` in decimal.
The stored flags are attributed to this final addition, even where their
numeric image coincides with an earlier flags value.

## What the composition establishes

The prefix checks both exact fill argument frames and returns, each fill's
independent whole-stack oracle, permitted writes, preserved registers and
the optional helper's global effect. The store phase checks the independent
field overlay from `docs/native_frame_stores.md`, including the temporary
flags-stack bytes, and stops before any import executes. The boundary
expectations above provide a separate check on the volatile inputs used by
that overlay.

This remains finite conformance in the pinned 32-bit flat-segment Unicorn
configuration. It does not identify a Windows structure or ABI, establish
nonzero segment-selector behavior, execute imported routines, prove whole
function return or justify a whole-program coverage promotion. The existing
caller and store receipts retain their original scopes and identities.

An external x86 SDK measurement now establishes byte-layout compatibility
for these fields; see `docs/windows_exception_layout.md`. It does not change
this receipt's scope or prove that the later imports consume valid objects.

## Reproduction

Use the optional Unicorn installation described in `docs/native_fill_conformance.md`:

```powershell
$env:PYTHONPATH = '.local_decompile/fill_runtime'
python -X utf8 scripts/itb_native_assertion_helper_import_handoff.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --pair data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_descendant_pair.json `
  --leaves data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_leaf_callees.json `
  --conformance data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_fill_conformance.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --caller data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_caller_fill.json `
  --stores data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_frame_stores.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_import_handoff.json
```

`verify-structure` omits the executable and does not load Unicorn. `build`
accepts `--output` instead of `--evidence`. Exact verification rejoins the
source receipts and complete body witnesses and reruns the composed matrix;
it does not rerun earlier whole-atlas scans or the full standalone fill matrix.
