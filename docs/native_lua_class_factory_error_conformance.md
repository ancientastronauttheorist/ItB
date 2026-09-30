# Native class factory rejection boundaries

This finite proof executes the factory's argument-count, type, numeric and
first-name-length rejection prefixes. Each case stops at the `lua_error`
import entry, before executing imported code or supplying any error response.
The preceding cdecl Lua calls receive explicit normal response contracts.
The proof neither returns from the factory nor models exception unwinding.

The exact executable SHA is
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Program facts and the factory-chain receipt are pinned. Their full 296-byte
factory body and both exact executable message strings are checked. Selected
code is the 174-byte prefix from RVA `0x002ec220` through exclusive
`0x002ec2ce`: 63 static sites and 62 executed sites. The first error-call
continuation at `0x002ec290` remains selected but never executes. Selection
ends before the second continuation's instruction.

The 344 cases comprise eight count rejections (responses 0, 2, 3 and
`0xffffffff`), eight type rejections (0, 3, 5 and `0xffffffff`), four numeric
rejections (1 and `0xffffffff`) and 324 length mismatches, each with two caller
profiles. Length cases combine six first-NUL offsets (0, 1, 2, 15, 16 and 255),
three byte patterns, three first-pointer alignments (0, 7 and 4095), and three
distinct supplied objlen responses (measured length plus one, plus two, or
`0xffffffff`). Page-crossing name reads are included.

The independent [request model](native_lua_class_factory_error_semantics.md)
specifies reached contracts only. `lua_gettop != 1` rejects first; otherwise
`lua_type != 4` rejects, then a nonzero `lua_isnumber` response rejects. Only
the remaining family reads the first tolstring pointer, measures its first
NUL using the native loop, and rejects when supplied objlen differs. No later
normal-path API, allocation or initializer is called. The native trace is
compared instruction by instruction to independently specified paths: 27,
33, 39, or 57 plus four times the measured length instructions.

The early guards select VA `0x0083ca60`, the invalid-construct message. The
length mismatch selects VA `0x0083ca88`, the extra-nulls message. These names
describe exact message selection; an arbitrary supplied length mismatch does
not prove that live input contains embedded NULs. A separate runtime Lua
controller consumes actual physical arguments and tracks message identity.
Its complete reached token trace agrees with the independent model, including
the terminal error request with no result. Large argument counts use a compact
symbolic prefix rather than allocating billions of argument tokens.

Let original ESP be S, factory frame F=S-4 and idle ESP B=F-36. Pushstring
entry is B-12 with `[continuation,L,literal]`. Its normal cdecl response pops
only the return address. The native body retains both argument words, pushes
L again, and calls the error import. Error entry is B-16=F-52 with
`[continuation,L,L,literal]`; continuation is VA `0x006ec290` or `0x006ec2ce`.
Every API frame, entry GPR, return word and exact deferred cleanup is checked.

At the stop, EBP=F, ESI=L and EBX is the staged pushstring target. EDI remains
the original caller word for early guards or the measured first-NUL length
for mismatch. EAX is the supplied pushstring result zero, ECX and EDX are its
supplied volatile words, and flags preserve that response under mask `0xcd5`,
including clear DF. The factory FS registration at F-12 remains active with
its saved original head. No epilogue or cookie verification has occurred.
Ordered native data events and every mapped page are checked against an
independent frame oracle, preserving caller ancestors, original buffers,
padding, IAT slots and literal pages.

The corpus executes 81,528 native instructions and receives 2,000 normal Lua
responses, reaching 344 error boundaries. All 15 exact controls reject for
their specified reasons. Controls cover caller and message memory, IAT
padding, cookie setup, FS chain, saved register, error return word, retained
literal, final registers and flags, API and error argument frames, altered
pushstring response, and wrong message identity.

Receipt:
`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_error_conformance.json`.
Canonical SHA:
`0e454398b0a47423e880932db975c82643358d6781115ced8989bb37a6a15952`.
File SHA:
`e43927841c891c22621ae2821e3e0f01c2d89487cde5aa22d45e23c9b1ec1d45`.
The CLI supports build, exact verify and PE-free verify-structure, with strict
deterministic UTF-8 LF bytes. Native rebuilding runs in isolated subprocesses.

Actual Lua VM and imported DLL behavior, error handling or unwinding,
factory return, allocation and initializer execution, security-cookie
verification, unrestricted pointer domains and program-wide accounting
promotion remain excluded. The complete conditional normal return has its
own separate [proof](native_lua_class_factory_conformance.md).
