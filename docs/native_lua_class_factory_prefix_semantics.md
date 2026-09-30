# Conditional normal factory-prefix model

`src/observatory/native_lua_class_factory_prefix_semantics.py` is a standalone
pure Python request model for the factory at RVA `0x002ec220`, stopping at the
opaque initializer entry `0x002eacf0`. It does not execute instructions or prove
conformance. The exact-build survey is `docs/native_lua_class_factory_survey.md`.

The interface is
`apply(name_bytes, *, state, first_pointer, second_pointer, userdata)`.
`state` is a synthetic Lua-state word. All four words must be exact Python ints
and nonzero uint32 values; bools and subclasses are rejected. `name_bytes` must
be exact bytes containing a NUL. If the first NUL is at offset `n`, only bytes
through that terminator are modeled. `first_pointer+n+1` must not wrap uint32;
this includes the native loop's cursor after reading the terminator. The second
pointer and userdata have no pointer arithmetic or dereference in this prefix.

The model supplies the seven normal Lua contracts in order: gettop returns 1,
type at index 1 returns 4, isnumber returns 0, tolstring returns `first_pointer`,
objlen returns `n`, tolstring returns `second_pointer`, and newuserdata requests
72 bytes and returns nonzero `userdata`. Both tolstring length-output arguments
are NULL. These responses are premises, not an implementation of Lua type,
number, string-length, or allocation behavior. In particular, synthetic bytes
after the first NUL do not determine the supplied objlen response.

Each `calls` record contains API name, full argument words, supplied result,
symbolic Lua before/after stacks, and the cdecl entry ESP offset from the idle
stack. Only newuserdata adds a modeled stack value. The initializer handoff
contains target/return RVAs, stack arguments `[state, second_pointer]`, and
constrained registers EAX=ECX=userdata, ESI=state, EDI=second_pointer. The
model assumes no equality of the two tolstring pointers and makes no assertion
about the second pointer's bytes. Claiming that those bytes are validated would
require an additional unchanged-Lua-string premise.

The inline length law has `n+1` byte reads and `71+4n` prefix instructions on
the normal nonzero-userdata path, excluding hook implementation instructions.
Its cursor subtraction is `(first_pointer+n+1)-(first_pointer+1)=n`.

For entry ESP `S`, let EBP `F=S-4` and idle ESP `B=F-36`. A cdecl API with
`k` arguments enters at `B-4(k+1)`; each ordinary API cleanup restores `B`.
Initializer entry is `F-48`, with stack words
`[0x006ec307, state, second_pointer]`. Local stores are `[F-16]=userdata`,
`[F-20]=userdata`, `[F-4]=0`. These offsets are returned in `frame`; actual
stack addresses, FS contents, handler execution, and cookie behavior are not
modeled. The preceding native setup pushes handler VA `0x007a6111`, saves
FS:[0], reads the cookie word at VA `0x00893f28`, pushes cookie XOR F, and
sets FS:[0] to `F-12`. No helper executes before the initializer call.

The standalone tests exhaust every NUL-containing byte sequence of length
one through four over `{0,1,65,255}`, independently count its nonzero prefix,
and verify opaque suffixes, distinct second pointers, request/frame laws,
detached outputs, exact type checks, and the cursor-wrap boundary. This is
finite model-law validation, not a native, Lua VM, allocation, exception,
ownership, source-class, or runtime-success proof. Rejected validation paths,
null userdata bypass, and initializer execution are outside this boundary.
