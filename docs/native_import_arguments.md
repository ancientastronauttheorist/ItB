# Conditional assertion import arguments

The exact six-instruction interval `[0x00379e20,0x00379e37)` connects the
previously verified frame to the argument for `UnhandledExceptionFilter`.
It covers 23 caller bytes. A symbolic transfer checks the argument and
register relationships under explicit external-call assumptions; it does
not execute an imported implementation.

Artifact: `data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_import_arguments.json`.
Canonical SHA-256: `a5db0b615b94a1291132a500fd025a74aeb4b0f8b78409f5d91bb30a6d4e282f`.
Raw SHA-256: `0c37b9bd564224d0d2593a3b9d9b573aadbf42e847b40587fada7a188c6c6933`.

The current PE's full owner instruction witnesses and three IAT, ILT and
import-name bindings are rechecked. These identify the first call as
`IsDebuggerPresent`, the second as `SetUnhandledExceptionFilter`, and the
exclusive stop call as `UnhandledExceptionFilter`.

## Conditional transfer

Let F be established EBP. Entry ESP is F-812. The first import takes no
stack arguments. After its assumed normal return, the caller pushes zero
and saves its result in EDI. The second import receives that zero argument;
its assumed callee cleanup restores ESP to F-812. The caller then computes
F-808 and pushes it. At the unexecuted third call, ESP is F-816 and its first
argument is the pointer F-808.

The pointer points to the eight-byte area containing F-800 and F-720.
The preceding SDK receipt establishes compatibility with `EXCEPTION_POINTERS`
and its two associated record layouts. This adds the imported function's
argument relationship, conditional on the preceding calls returning with
the declared stack and memory properties.

The model preserves nonvolatile registers across imported calls, allows
arbitrary EAX/ECX/EDX/flags results, and assumes caller-owned stack memory at
F-812 and above is preserved. Lower scratch memory and global state remain
unspecified. EDI at the stop holds the first import's opaque return value;
ECX, EDX and flags hold opaque values from the second. The model does not
infer that the first return is exactly one when nonzero.

The call instruction at `0x00379e37` remains outside this slice. The argument
is at `[ESP]` before that instruction. It would be at `[ESP+4]` after the
call pushes its return address. No claim about the third import's return,
side effects or continuation follows from this argument construction.

## External contract and limits

Microsoft documents [IsDebuggerPresent](https://learn.microsoft.com/en-us/windows/win32/api/debugapi/nf-debugapi-isdebuggerpresent)
as returning zero or nonzero, and [SetUnhandledExceptionFilter](https://learn.microsoft.com/en-us/windows/win32/api/errhandlingapi/nf-errhandlingapi-setunhandledexceptionfilter)
as taking a filter pointer, with null selecting default handling. The
[x86 stdcall convention](https://learn.microsoft.com/en-us/cpp/cpp/stdcall?view=msvc-170)
assigns argument cleanup to the callee.
[UnhandledExceptionFilter](https://learn.microsoft.com/en-us/windows/win32/api/errhandlingapi/nf-errhandlingapi-unhandledexceptionfilter)
takes an exception-pointer pair. These interface references support the
declared model; they are not observations of this game's imported execution.

Normal returns and caller-owned frame preservation are premises. Nonreturning
calls, exceptions, memory corruption, native object alignment, actual DLL
resolution, API side effects, complete function behavior and whole-program
coverage remain outside this proof. No debugger, process filter or game state
is changed by the analysis.

## Reproduction

```powershell
python -X utf8 scripts/itb_native_assertion_helper_import_arguments.py verify `
  --executable "B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe" `
  --pair data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_descendant_pair.json `
  --program-facts data/observatory/programs/windows_build_13725832_31fe35265598_program_facts.json `
  --handoff data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_import_handoff.json `
  --layout data/observatory/programs/windows_build_13725832_31fe35265598_windows_exception_layout.json `
  --evidence data/observatory/programs/windows_build_13725832_31fe35265598_native_assertion_helper_import_arguments.json
```

`verify` rereads the exact PE and rebuilds the static transfer receipt.
`verify-structure` omits the executable. Neither command needs an emulator
or invokes an imported implementation. `build` emits deterministic UTF-8
JSON to standard output and omits `--evidence`.
