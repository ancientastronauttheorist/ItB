# Conditional failure return chain

The final failure call now has an independent specification for its complete
40-byte wrapper at RVA `0x00357b42`, the parent's final nine bytes at
`0x00357c5c`, and the owner's four-byte continuation at `0x00379e5f`.
These contain 12, four and three instructions respectively. The receipt
models the path on which all four imported calls return normally under
explicit summaries; it does not establish that this path occurs on Windows.

## Calls and stack lifetime

Let G be the failure frame, F=G+816 the preceding owner frame, and H=G-816
the wrapper frame after its prologue. The wrapper calls
SetUnhandledExceptionFilter with zero, UnhandledExceptionFilter with the
supplied pair address, GetCurrentProcess with no arguments, and
TerminateProcess with that returned handle and status `0xc0000409`.
Fresh IAT, ILT, descriptor and name witnesses bind all four imports.

The exit status is pushed before GetCurrentProcess and must survive that
zero-argument call. Import-entry ESP offsets relative to G are -824, -824,
-824 and -828. Their assumed stdcall return increments are eight, eight,
four and twelve bytes, including return addresses.

The import summaries preserve nonvolatile registers and words in G-relative
intervals [-816,-804), [0,8) and [816,824). GetCurrentProcess additionally
preserves [-820,-816), the pending status. The integer model forgets every
unprotected word after each abstract import. Pair contents, global records
and other memory have no preservation guarantee.

The wrapper return reaches `0x00357c61` with EBP=G and ESP=G-808. The parent
return reaches `0x00379e5f` with EBP=F and ESP=F-808. The owner continuation
then restores the supplied word at F and transfers to the supplied word at
F+4, ending at ESP=F+8. EAX is the last import's return value; ECX, EDX and
flags retain that import's opaque outputs.

These outer words are values observed at this slice's entry. The earlier
feature-query summary protected only the failure header, so recovering the
original owner's saved EBP and return target would require an additional
preservation premise. This receipt does not silently add that guarantee.

Microsoft documents GetCurrentProcess as returning a current-process pseudo
handle, and successful self-termination as a path on which TerminateProcess
does not return. Those platform semantics are separate from this abstract
normal-return branch. See
[GetCurrentProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getcurrentprocess)
and [TerminateProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess).
If any import does not return normally, the later modeled instructions and
final return are not established.

## Evidence and reproduction

The 192 integer-model cases vary 16 frame alignments, two handle words, three
last-import return words and two observed outer-word pairs. They verify all
19 instructions, ordered import arguments and the conditional final interface.
They are not actual import executions or a claim that every vector can occur
with real Windows implementations.

Artifact: `windows_build_13725832_31fe35265598_native_assertion_helper_failure_return.json`.
Canonical SHA-256:
`0971cfa63e07affc80e0574319382099d9c41b29b5a380d1eb70a40e832a3444`.
Raw SHA-256:
`b3c17b81879e71274072ca47e94efa454ab1a5690cd0134152593429e356cca4`.

`scripts/itb_native_assertion_helper_failure_return.py verify` takes
`--executable`, `--evidence`, `--dispatch`, `--frontier`, `--tail` and
`--program-facts`. It freshly verifies the exact grammar and source joins.
`verify-structure` omits the executable; `build` omits the evidence and emits
deterministic UTF-8 JSON. Independent tests also check byte-identical CLI
output from the exact executable. No whole-program accounting is promoted.
