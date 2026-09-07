# Conditional allocation retry protocol

The wrapper at RVA `0x003574db` is 51 bytes/20 nodes. Its behavior is now
specified as a finite response protocol with explicit normal-return premises
for four callees. The role labels below describe their place in this protocol;
they do not establish the callees' complete implementation or ownership.

It first calls the candidate function at `0x00379f52` with the request word.
A nonzero result returns to its caller. A zero result calls `0x0038bbc4`
with the same request. If that response is nonzero, the wrapper retries the
candidate. Otherwise it calls `0x0035848f` when the request is `0xffffffff`,
or `0x003435bc` for other requests. If either of those calls returns normally,
the wrapper retries. No failure-call nonreturn or loop termination is inferred.

The standalone protocol accepts at most 64 supplied responses. Each record
must match the next expected call role. Unused or mismatched records fail
validation. An exhausted transcript is accepted only when an explicit
frontier stop is requested; it denotes the next unresolved call, not a
successful allocation.

## Calls and frame preservation

Let S be entry ESP and F=S-4. Candidate and response calls push the request
at F-4 and their CALL continuation at F-8. The two failure calls have no
pushed request and instead write their continuation at F-4. The model checks
these different stack effects and the caller's later POP of the temporary
argument. Under a successful finite transcript, the wrapper restores EBP,
returns the last nonzero candidate value in EAX, retains the request in ECX
and ends with ESP=S+4 (cdecl).

Every supplied callee response preserves EBP, nonvolatile registers and all
modeled memory, including the original caller request and temporary pushed
argument. That memory preservation is an explicit summary premise; cdecl
alone does not guarantee it. EAX responses and sampled ECX, EDX and flags
are supplied by the experiments. Final TEST paths leave AF undefined.

The upstream vector-request helper emits only nonzero byte requests below
`0xffffffff`: small requests are multiples of eight; large requests are
three modulo eight and at most `0xfffffffb`. Consequently the special
`-1` branch is excluded for that composition **if the request stays stable
across calls**. Initial request provenance alone is insufficient if a callee
can modify the caller's argument word.

## Validation and receipts

The graph receipt checks 504 cases, with 224 returns, 280 frontier stops,
1,344 summarized calls and five semantic mutations. A separate Unicorn 2.1.4
receipt checks 640 cases, equally divided between returns and frontier stops.
It executes all 20 wrapper sites, including 1,600 CALL instructions. At each
callee entry a hook stops before any callee instruction executes, checks the
actual continuation and argument, supplies the declared volatile outputs and
resumes the wrapper. There are zero callee instruction executions.

The independent replay oracle checks protocol transitions, all general
registers, defined flags, the complete stack and ordered native accesses.
Host inspection reads are separate from native memory events. A changed
candidate response must change the expected outcome and fail the oracle.
Independent semantic and conformance reviews passed. All 30 focused tests
passed, including deterministic exact-executable and replay subprocess CLI builds.

`scripts/itb_native_allocation_retry_semantics.py` uses `--program-facts`
and `--allocation-semantics`. Its corresponding conformance CLI uses
`--semantics`. Both offer `build`, `verify` and `verify-structure`;
exact commands require `--executable` and verification requires `--evidence`.

Published filenames share
`windows_build_13725832_31fe35265598_native_allocation_retry_`:

| Receipt | Canonical SHA256 | Raw UTF-8/LF SHA256 |
| --- | --- | --- |
| `semantics.json` | `e871c34df5d80d61c2bc8b26d24f053559b966f1d80d58e3df195cc831d2dbe2` | `ca5fde2a0b1fb71ab4e6606a0e32b2fdf8aaae788972332889756e096cf21bfc` |
| `conformance.json` | `92c7ffc148c0a8898c5cc6cb3654282fc94ffe97ed052bbb7d453db8058d44dd` | `eb05dedf3110e7a3a90cfcc63d609494f13d7253990db3debc3830b77bc68b61` |

Actual candidate, handler and failure behavior remain separate work. No heap
operation, successful allocation guarantee or whole-program promotion follows
from these conditional protocol receipts.
