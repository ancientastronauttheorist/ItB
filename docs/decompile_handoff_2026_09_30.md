# September 30 decompilation checkpoints

The authorized working branch is `codex/full-decompile`, explicitly selected
by the user despite the general main-only policy. The time-bound request is
to continue useful validated work until **September 30, 2026, 5 pm
America/Chicago = 22:00 UTC**. Stop new work then, finish current validation
safely, push the final checkpoint, verify protected files and pause the
`decompile-until-5-pm` continuation heartbeat. The full game remains unfinished.

## Pushed checkpoints

| Commit | Completed tranche |
|---|---|
| `07d24a0c` | AGENTS.md now tells subagents to inherit the primary model, with no explicit model override. |
| `2ca21ff3` | Actual callback local record and incoming registers mapped to class prefix/external-spare return. |
| `de119fa2` | Shared 13 Lua import targets, heap allocation target and three literal pages for marker/table composition. |
| `60ebc3fb` | Independent callback logical class operation and continuous Lua registry/table request model. |
| `30ec0e1e` | Sealed one-machine external-spare callback, markers, class operation and both table transfers. |
| `5344217e` | Actual callback record mapped through first-null vector allocation and small old-vector growth/copy/free. |
| `c4c934b4` | Sealed continuous callback through first-null and small old-full vector growth. |
| `f5b5186e` | Sealed normal factory prefix through its actual initializer handoff. |
| `5df38776` | Sealed continuous factory and 37-instruction initializer prefix through record-helper entry. |
| `89941b57` | Sealed native self-linked record allocation and construction through actual userdata offset 52 store. |
| `3c08d3c0` | Sealed continuous complete normal factory and initializer returns with actual record, registry identities and closure upvalue. |
| `15bc0fae` | Sealed all four factory rejection prefixes through lua_error import entry. |
| `0db08866` | Sealed returned-callback argument-marker rejection with both actual native marker helpers. |

The earlier [September 11 handoff](decompile_handoff_2026_09_11.md) records the
existing standalone tree, balancing, insertion, vector, marker and table proofs.
Do not repeat those tranches or promote whole-program accounting from these
finite proofs.

## Continuous external-spare callback

[Documentation](native_lua_class_callback_conformance.md) and
[receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_callback_conformance.json):

- Canonical SHA: `e4bc62a4677e0bf190d861cc1749fc0346ee048c8cb39d112ed2c4a36f151cfa`.
- File SHA: `3ed08f6a7a82749ff1e87b01893849e320844f0a207dc4d0862d8be4609c9218`.
- 1,152 cases; 874 selected sites; 778 executed sites; 2,280 unique selected bytes.
- 1,611,648 native instructions; 43,008 supplied API calls; 1,584 tree allocations.
- Ten exact controls; independent GO; 198 focused tests passed, no skips,
  including byte-identical exact CLI rebuild.

All native helpers execute continuously in one Unicorn machine, receiving the
actual current memory/register state. The runtime API interpreter carries one
Lua token stack and retains four registry identities before returning zero
results. The independent model checks class transfer, original record append,
copied source word, filtered assignments, parent-owned cells and ancestors.
Imported Lua and heap APIs remain explicit supplied normal contracts. This
does not establish real VM/table/metamethod behavior or arbitrary domains.

The stack-local class record is above both finite vector ranges. Exactly three
sites from the legacy-record class receipt cannot execute here:
`0x002eb1c5`, `0x002eb1c8`, `0x002eb1ca`. Every other inherited class site,
every table site and every normal callback site is required. The record
argument is derived from current child initial pages at S+4; no separate
argument metadata should be invented.

## Completed growth caller mapping

[Documentation](native_lua_class_growth_record_caller_mapping.md):
first-null and old-full helpers accept the checked local `[0,SOURCE_OBJECT]`
at S+28, callback GPRs and real `2ec1bd` continuation. Models preserve original
caller bytes and record words through growth, native copy and supplied free.
Validation: 147 passing tests, no skips, 48 native caller successes and four
exact controls. Original 576-case first-null and 1,536-case old-growth receipts
rebuilt byte for byte. Original pure suites also passed 43 tests with two skips;
those native tests ran separately as part of the complete validation.

## Completed continuous growth callback

[Documentation](native_lua_class_callback_growth_conformance.md) and
[receipt](../data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_callback_growth_conformance.json):

- Canonical SHA: `59a2123f649633045e35102d2900cf936048f7252095152a27cee6774d60d443`.
- File SHA: `b0fb268b5e364c807fd3b62ae5f6716aa137665ba0c24cfd99a01d8d4cd7c723`.
- 2,304 cases, split equally between first-null and old-full vector families.
- 945 executed sites; 1,115 selected sites; 2,905 unique selected bytes.
- 3,636,288 native instructions; 86,016 supplied API calls; 5,472 allocations;
  1,152 frees; 2,304 logical assignment requests.
- All 26 exact controls passed; independent GO; 428 focused tests passed with
  no skips, including the byte-identical exact CLI rebuild.
- Original external-spare receipt remained byte-identical across its 33-test
  suite after the common runtime machinery changed.

The opt-in logical model accepts external full live sizes zero through three.
Each family executes its actual native class helper continuously with the
callback and table transfers. Supplied heap calls are distinguished by exact
native continuations and checked requests. Larger vectors, internal storage,
error paths and real VM behavior remain outside this finite proof.

## Completed normal factory prefix

[Documentation](native_lua_class_factory_prefix_conformance.md): 216 cases,
83 selected sites, 71 executed sites and 231 selected bytes. Exact execution
covered 56,952 native instructions and 1,512 supplied API calls. All 15 controls
were rejected for their specified reasons. Model and conformance validation
passed 102 tests with no skips, including the byte-identical exact CLI rebuild.
Canonical SHA: `cebf742aac9945f22829e2d3b1b387ff618840217b3c9a2330a8335ca3a0d0ed`.
File SHA: `dc56cc73bf36a0f1e642638f5d5f1b7ad80f7121f45dde197f0256f642bd9955`.

## Completed initializer prefix composition

[Documentation](native_lua_class_factory_initializer_prefix_conformance.md):
216 continuous factory/initializer cases, 120 selected sites, 108 executed
sites and 391 selected bytes. Native execution covered 64,944 instructions,
including 7,992 initializer instructions, and 1,512 supplied Lua API calls.
All 22 controls passed; independent GO; 67 new focused tests passed with no
skips, including the byte-identical exact CLI rebuild. A preceding 124-test
gate also proved the original factory receipt remains byte-identical.
Canonical SHA: `abd888a364076edd037f460a0515b9586610218f9e5437aa4f67ab0cd972c47e`.
File SHA: `9f64ec4a0124e1ad7f52cda34c7faaa949e924484df55e9a8f40c24ab23e827f`.
The 14 fixed word writes, four untouched words, second pointer at userdata
offset 16, nested FS chain and overwritten argument cell are checked. The
machine stops at `0x0007c600` before the helper's first instruction.

## Completed native record construction

[Documentation](native_lua_class_factory_record_conformance.md): 1,728 cases,
195 selected sites, 160 normal executed sites and 576 bytes. All native factory,
initializer-prefix, record-helper, retry, thunk and heap-wrapper instructions
execute continuously; only seven Lua responses and one successful HeapAlloc
response per case are supplied. Execution covered 609,408 native instructions,
12,096 Lua API calls and 1,728 heap calls. All 30 controls passed, independent
GO, and 58 focused tests passed with no skips including the exact CLI rebuild.
A preceding 103-test gate proved both earlier factory receipts remain
byte-identical after adding the fixture and heap hooks.
Canonical SHA: `94fb1682f5d89c131e6fe2eab62e926f0f4b71494d0fa12a5e89762dd8253a79`.
File SHA: `bc514c41fd8c2779e4e8c97aee406d4c05b4cbada41aa5daaf9e474e57372c23`.
All three self links, the two-byte marker and untouched bytes 14 through 23
are checked, including a page-crossing DWORD store. The actual returned
record is stored at userdata offset 52. The endpoint is `0x002ead94`.

## Completed normal factory return

[Documentation](native_lua_class_factory_conformance.md): 5,184 continuous
cases, 365 selected sites, 302 executed normal sites and 1,089 selected bytes.
The complete factory, initializer, record helper and allocation bodies execute
in one machine. Supplied contracts total 176,256 Lua calls and 5,184 heap calls;
native execution totals 2,564,352 instructions. All 38 controls passed. The
dedicated 58-test gate passed without skips, including a byte-identical exact
CLI rebuild. A preceding 236-test model and integration gate passed, rebuilding
all three earlier factory receipts byte-identically.

Canonical SHA: `d8b36d30d732467edb54396ba22a3cd2a167dca15780f3020df18256c617dbcf`.
File SHA: `29dc4376f28a537d0052c2dbd39c90328e8213fc029932fe3c16ee9ec1df291a`.
All 18 userdata words, actual record stores, every mapped page, 34 physical API
frames and an independent Lua token trace are checked. Both native functions
return; original nonvolatile registers and FS head are restored. The factory
returns one closure with the actual userdata as its one upvalue. Metatable,
registry and global assignments remain conditional supplied requests. The
closure target is not invoked, and the epilogues do not verify security cookies.

## Completed factory rejection prefixes

[Documentation](native_lua_class_factory_error_conformance.md): 344 cases
cover argument count, type, numeric and first-name-length rejection. The
174-byte selected prefix has 63 static sites and 62 executed sites. Execution
covers 81,528 native instructions and 2,000 supplied normal Lua responses,
stopping at 344 lua_error import entries without executing imported code or
supplying error responses. All 15 controls passed. Independent GO and 133
focused tests passed without skips, including the byte-identical exact rebuild.

Canonical SHA: `0e454398b0a47423e880932db975c82643358d6781115ced8989bb37a6a15952`.
File SHA: `e43927841c891c22621ae2821e3e0f01c2d89487cde5aa22d45e23c9b1ec1d45`.
The independent short-circuit model, runtime message identity, actual literal
selection, retained pushstring argument cells, active FS chain, exact API GPRs,
ordered data events and all mapped pages are checked. A supplied length
mismatch proves the chosen message, not the live cause of an embedded NUL.
Error handling, unwinding, factory return and live VM behavior remain excluded.

## Completed returned-callback argument rejection

[Documentation](native_lua_class_callback_error_conformance.md): 432 cases,
76 static sites, 66 executed sites and 223 selected bytes. Both actual native
marker helpers execute continuously with the callback; a truthy upvalue passes
and an absent, nil or false argument marker rejects. Execution covers 35,712
native instructions, 4,608 supplied Lua responses and 864 native marker calls,
ending at 432 lua_error import entries. All 18 controls passed. Independent GO
and 115 focused tests passed with no skips, including the exact CLI rebuild.

Canonical SHA: `1c720f1a11c848aa2e5c9ef31dbb4aea6eb9e24bcb1867b30f463cb2d35ff988`.
File SHA: `970e677a0ea99e2ae9eabf27fb825fd70f0efdd2845e991b7d7f6ce89d2b9a6e`.
Independent child frame corollaries, physical API GPRs, ordered events and all
pages preserve whole-EAX evidence, while the actual parent guards inspect AL.
The token model and runtime observer verify Lua truth and prefix restoration.
The retained pushstring frame is checked at the unexecuted error boundary.
No live VM invocation, unwind, callback return or cookie verification follows.

## Completed callback upvalue assertion prefixes

[Documentation](native_lua_class_callback_assertion_prefix_conformance.md):
192 cases check null upvalue userdata and absent, nil or false upvalue markers.
The 185-byte callback/marker union has 65 static and 59 executed sites. Actual
execution covers 8,256 instructions, 720 supplied Lua responses and 144 native
marker calls, ending at 192 native assertion-helper entries. No helper
instruction or response executes. All 16 controls passed, independent GO and
88 dedicated native/model tests passed without skips. A combined 146-test
gate also rebuilt the complete normal factory receipt byte-identically after
adding the next proof's optional boundary oracle.

Canonical SHA: `b6486105640001ae644f9ea2023c98ca62626df5f1ab2c2041ba2dea2879484e`.
File SHA: `566da6057527a877f2441b7b29075a4742cc32c1bb65e6952f3e50c1ae0eb861`.
The two exact three-word requests and CALL continuations, high-EAX/AL guard
distinction, cookie-only frame, restored argument prefix, physical API GPRs,
ordered events and all mapped pages are checked. Expression and filename
contents, assertion-helper behavior, unwind and callback return remain open.

## Active continuation

The normal factory prefix now reaches initializer entry `0x002eacf0`.
Its seven Lua API calls remain supplied contracts. The first
`lua_tolstring` pointer is measured by the inline NUL loop; the second pointer
is passed to the initializer. Preserve independent pointer routing rather
than assuming the pointers or bytes are equal. Error arms and null-userdata
bypass are separate boundaries. No initializer, ownership or exception-handling
claim follows from that first handoff alone. Its following 37 initializer
instructions are now checked by the separate composition above, and the normal
return is closed by the complete proof. Factory rejection prefixes are also
closed through lua_error entry. The callback argument rejection is also closed.
Both callback upvalue assertion prefixes are now checked. Next useful
continuation: execute the factory and initializer through the context guard
minus-two branch and its native assertion-helper entry. Preserve the actual
record allocation, two registry identities, 18 reached Lua contracts, active
nested FS chain and exact three-word native boundary frame. Keep
the supplied normal registry context, three references, graph and ID-map
pointers explicit. Prior-reference unref arms, assertion, real VM effects and
arbitrary registry results remain outside the conditional proof.

## Environment and preservation

Exact PE: `B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe`.
SHA-256: `31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Native runtime uses Python 3.13, private Capstone 5.0.7 and Unicorn 2.1.4:

```powershell
$env:PYTHONPATH='.local_decompile/fill_runtime;.'
$env:ITB_EXACT_EXE='B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe'
```

Native execution belongs in isolated subprocesses and tests run serially.
Publish only safe normalized instruction witnesses, synthetic vectors, facts
and digests. The executable and raw inspection files remain private. Sealed
receipts use deterministic UTF-8 LF and exclusive publication after checking
canonical and file identity.

Protected original dirty work: achievements, weapon penalties, default log,
resist/failure recordings, active session, loop commands, lightning-war test,
four default board/solve/threat JSONs and smoke-run notes. Thirteen baseline
file hashes live privately at `.local_decompile/sep30/protected_work.json`.
They were verified unchanged after callback sealing. Never stage, reset or
revert this work. No live game actions were taken for these decompilation
tranches. The user asked to stop using expensive Astra agents; the remaining
older reviewer was stopped and subsequent subagents were freshly spawned
with inherited model settings and no Astra override.
