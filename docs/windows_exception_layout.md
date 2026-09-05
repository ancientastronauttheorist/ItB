# Windows x86 exception-layout compatibility

An independently compiled x86 SDK probe supplies an external layout reference
for the assertion frame. It uses `sizeof` and `offsetof` on the installed
Windows SDK declarations, with four-byte pointers. The measured sizes are
eight bytes for `EXCEPTION_POINTERS`, 80 for `EXCEPTION_RECORD` and 716 for
`CONTEXT`. These match the two-pointer area and the adjacent cleared regions
already proved in `docs/native_caller_fill.md`.

The sealed probe checks 33 top-level fields and retains hashes for all 162
included headers. It uses MSVC tools 14.29.30133 (compiler file version
19.29.30154.0) and Windows SDK 10.0.19041.0, with explicit x86 include and
library paths. The probe's source contains independent measurement requests;
it includes the SDK types instead of redeclaring them.

Artifact: `data/observatory/programs/windows_build_13725832_31fe35265598_windows_exception_layout.json`.
Canonical SHA-256: `c71a3142e5fc172a6a686a1b83f3bce3a9af181142c8386276ed481f2861acef`.
Raw SHA-256: `dc11ac81b491707444e5b54cbe6edbf8b25d9985b757d9e4fe4c444e8fb5cd55`.

This establishes layout compatibility with the measured SDK. It does not
prove which SDK or compiler built the game, nor that an imported routine
actually consumes these objects. The current exact emulation stops before
the first import; that later call sequence needs its own proof.
`docs/native_import_arguments.md` now supplies a conditional symbolic join to
the third import's argument, with normal-return and frame-preservation
assumptions. Actual imported execution remains outside both receipts.
The byte-offset correspondence also does not establish native object
alignment or the validity of typed pointers for every synthetic frame address.

## Field correspondence

All offsets below are relative to established EBP F. The frame-store receipt
provides the write widths and value sources. The SDK supplies the field
offsets and declared widths.

| Frame region | Compatible SDK object | Observed field writes |
|---|---|---|
| F-808, eight bytes | `EXCEPTION_POINTERS` | Pointers to F-800 and F-720 |
| F-800, 80 bytes | `EXCEPTION_RECORD` | Code, flags and address |
| F-720, 716 bytes | x86 `CONTEXT` | Flags, six selectors and ten other register fields |

The exception record's code and flags receive the incoming words at F+12
and F+16. Its address receives the word at F+4. Its chained-record pointer,
parameter count and parameter array retain the preceding zero fill.

The context flags word is 65537, equal to the probed x86 `CONTEXT_CONTROL`
constant. The EAX-named field receives F-720, computed inside the store
slice. ECX, EDX and EFLAGS receive the values derived in
`docs/native_import_handoff.md`; these names do not turn those values into
an original caller-entry context capture.

Each selector store writes two bytes into a four-byte SDK field. The upper
halfword stays zero from the earlier fill. The distinction between an
instruction's write width and a declaration's field width is preserved in
the overlap map.

## External reference

Microsoft documents the architecture-specific [x86 CONTEXT layout](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-context-r2),
the [exception record](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-exception_record),
and the [pair of exception and context pointers](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-exception_pointers).
The local SDK probe measures their concrete sizes and offsets for the pinned
x86 build configuration. Proprietary headers and compiled probe binaries
remain outside Git; only independently authored tools and normalized facts
are retained.

## Reproduction

```powershell
python -X utf8 scripts/itb_windows_exception_layout.py verify `
  --stores data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_frame_stores.json `
  --handoff data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_import_handoff.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_windows_exception_layout.json
```

`verify` compiles and runs the independent probe and compares the measured
receipt. `verify-structure` needs neither Windows nor the compiler. `build`
omits `--evidence` and emits deterministic UTF-8 JSON bytes to standard output.
It does not write or replace a public artifact. Probe work products and
diagnostic output are retained under ignored `.local_decompile/sdk_layout/`.
