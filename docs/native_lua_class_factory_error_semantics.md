# Conditional factory rejection model

`src/observatory/native_lua_class_factory_error_semantics.py` is an independent
pure Python request model of the factory's four rejection families. The endpoint
is entry to the `lua_error` import, before executing the DLL. It supplies no
lua_error response and proves neither nonreturn nor unwind/exception behavior.
Earlier APIs, including message pushstring, have conditional normal-return
contracts. No native instructions or Lua VM effects execute in this model.

The interface is
`apply(*, state, argument_count, type_result, number_result, first_pointer,
name_bytes, object_length)`. State is an exact nonzero uint32 int. Reached API
responses are exact uint32 ints; bools and int subclasses are rejected. Only
contracts actually reached by the sequential guards are inspected:

| Guard | Rejection reason | Unused later contracts |
| --- | --- | --- |
| gettop response differs from 1 | `argument_count` | Type, number, pointer, bytes, length |
| type response differs from 4 | `type` | Number, pointer, bytes, length |
| isnumber response differs from 0 | `numeric` | Pointer, bytes, length |
| First-NUL length differs from objlen response | `name_length` | None |

The first three families select VA `0x0083ca60`, literal
`invalid construct, expected class name`. The final family selects VA
`0x0083ca88`, literal
`luabind does not support class names with extra nulls`. Response comparisons
use exact word equality or zero/nonzero tests; high-bit words are not inferred
to be valid Lua types, lengths, or numbers.

For the length family, the first pointer must be exact nonzero uint32 and the
synthetic name must be exact bytes containing a NUL. If its first NUL is at
offset n, the model reads only bytes through that terminator, and requires the
cursor `first_pointer+n+1` not to wrap. Later synthetic bytes are ignored. Page
crossings are permitted under a readable-byte premise; mapping/protection is
not checked. The supplied objlen response is compared to n. Equal lengths
select an accepted normal prefix and are rejected as outside this error model.

`calls` records the reached supplied responses, followed by pushstring with the
chosen literal and the lua_error entry request. Each includes full logical
arguments, symbolic stack snapshots, and literal role. Pushstring's zero result
is a void comparison placeholder. The terminal lua_error result is `None`;
identical before/after snapshots mean the import has not executed. They do not
assert that calling lua_error would leave a VM stack unchanged or return.

`initial_lua_stack` uses individual argument tokens for counts zero through
three. Larger uint32 counts use one compact `('arguments', count)` prefix
token, retaining cardinality without an unbounded allocation. The message token
is appended and remains in `error_entry_lua_stack`. `lua_stack_delta=1` records
that conditional message push, regardless of compact representation.

For factory entry ESP S, let EBP `F=S-4` and idle ESP `B=F-36`. Message
pushstring entry is `B-12=F-48`, with stack words `[return, state, literal]`.
After its normal return, both argument words remain on the native stack.
lua_error entry is `B-16=F-52`, with words
`[return, state, state, literal]`. The error return-address word is VA
`0x006ec290` for the first three families and `0x006ec2ce` for name-length
mismatch. These are machine call-frame words, not a claim that lua_error
returns. `endpoint` pins the call/IAT/return RVAs; `frame` exposes both entry
layouts.

Tests cover all four families, independent sequential short-circuiting with
poisoned irrelevant values, high-bit response boundaries, exhaustive small
first-NUL byte families, accepted-prefix exclusion, strict reached types,
cursor/page boundaries, exact literals/frames, and detached outputs. They
verify model laws only. Actual errors, VM mutation, unwinding, exceptions,
runtime reachability, source-level class identity, and successful allocation
remain outside this boundary.
