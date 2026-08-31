# Native Lua `class` factory survey

Status: read-only static research checkpoint. This document follows one
build-bound native closure chain published under the exact Lua global key
`class`; it does not reconstruct source or prove runtime behavior.

## Bound evidence

The scope is the x86 Windows `Breach.exe`, build `13725832`, SHA-256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
All RVAs are image-relative.

The chain composes these exact artifacts:

- Program-facts atlas, canonical SHA-256
  `631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803`.
- Direct Lua import-call census, canonical SHA-256
  `07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608`.
- Table-key provenance census, canonical SHA-256
  `8b8cab571c3c8945dae440933107022b35eed28b4c806a35188202bd52073db6`.
- Terminal-disposition census, canonical SHA-256
  `74b762e486611a6dc71325276d9e8e92b7894de30f99bacf9e301e894c85bb85`.

Lua 5.1 API interpretations use `LUA_GLOBALSINDEX == -10002`,
`LUA_REGISTRYINDEX == -10000`, and `lua_upvalueindex(1) == -10003` as ABI
premises. They do not show that a particular Lua state, table, or closure
exists at runtime.

## Publication-to-result chain

The table-key provenance census proves that constructor `0x002e6900` creates a
zero-upvalue native closure targeting `0x002ec220` at `0x002e6ba1`, with exact
key literal `class` at RVA `0x0043bf98`, and supplies it to
`lua_settable(L, LUA_GLOBALSINDEX)`. It is a static global-environment
assignment grammar, not proof of a durable export or lookup success.

The published callback has a 296-byte atlas body, SHA-256
`8a9c01de90919d67efa728e4ed9e41e9f9d68fa7f0faf0e8abbdd809cce91f9e`.
On its normal result path it creates a one-upvalue closure targeting
`0x002ec110` at `0x002ec328`; the terminal-disposition census proves that it
then returns exactly one Lua result. The returned callback has a 269-byte
atlas body, SHA-256
`a138a00ca47281aa3b4fb0db11a3aa5e875616a57b3684f7598e4b0517b900e3`.

```text
constructor 0x002e6900
  class key / global-environment setter
    -> factory callback 0x002ec220
      returns one closure carrying one userdata upvalue
        -> returned callback 0x002ec110
          returns zero results on its normal path
```

The arrows above are exact construction and return relations, not runtime
reachability, semantic class identity, or source-level method syntax.

## Factory callback grammar (`0x002ec220`)

The callback accepts a narrow normal path:

| check or action | RVAs |
| --- | --- |
| require exactly one Lua argument | `0x002ec24c` through `0x002ec25e` |
| require Lua type 4 (string) at argument 1 | `0x002ec263` through `0x002ec26f` |
| reject a string accepted by `lua_isnumber` | `0x002ec274` through `0x002ec27f` |
| error literal: `invalid construct, expected class name` | `0x002ec281` through `0x002ec28a` |
| obtain C string for argument 1 with a NULL length-output pointer | `0x002ec293` through `0x002ec298` |
| compute its NUL-terminated length and compare against `lua_objlen(1)` | `0x002ec2a3` through `0x002ec2bd` |
| error literal: `luabind does not support class names with extra nulls` | `0x002ec2bf` through `0x002ec2c8` |
| allocate 72-byte Lua userdata | `0x002ec2e1` through `0x002ec2e4` |
| native initializer of that userdata | direct call `0x002ec302 -> 0x002eacf0` |
| push the validated name, duplicate the userdata, and set global environment entry | `0x002ec307` through `0x002ec31a` |
| create returned closure with one upvalue | `0x002ec320` through `0x002ec328` |
| declare one Lua result | `0x002ec331` |

Under the Lua 5.1 stack model, immediately before the global setter the
retained stack fragment is `A,U,N,U`, where `A` is the original argument,
`U` the new userdata, and `N` the validated name. The global `lua_settable`
consumes `N,U`, leaving `A,U`; `lua_pushcclosure(..., 1)` consumes the userdata
as its one upvalue and pushes a closure. The terminal result count then retains
that closure as the single return value.

This is the strongest local static claim: on the ordinary non-error path, the
published callback validates one nonnumeric Lua string without embedded NUL,
creates a 72-byte userdata initialized by `0x002eacf0`, writes that userdata
under the string key through the Lua global-environment table setter, and
returns a closure carrying that userdata as its only upvalue. Because the
setter is `lua_settable`, not `lua_rawset`, it does not establish a raw store
or absence of metamethod effects.

## Returned callback grammar (`0x002ec110`)

The returned callback starts by retrieving its sole upvalue at
`lua_upvalueindex(1)` with `lua_touserdata` at `0x002ec132`. It then calls
`0x002eb560` twice:

| checked item | setup / helper call |
| --- | --- |
| upvalue | `edx = -10003`, `ecx = L`, call at `0x002ec15b` |
| Lua argument 1 | `edx = 1`, `ecx = L`, call at `0x002ec17f` |

`0x002eb560` uses `lua_getmetatable`, `lua_gettable`, and `lua_toboolean` to
test a metatable field keyed by exact literal `__luabind_classrep` (RVA
`0x0043c738`). The callback's normal continuation requires that helper to
return nonzero for both values. A failed upvalue check takes an assertion path
through helper RVA `0x00379cc2` at `0x002ec170`. A failed argument-1 check instead
pushes exact literal `expected class to derive from or a newline` (RVA
`0x0043c99c`) and calls `lua_error` at `0x002ec195`. It next converts argument
1 with `lua_touserdata` at `0x002ec1a1`.

The callback passes the upvalue in ECX and a two-word local whose second word
is the argument userdata to `0x002eb140` at `0x002ec1b8`. Within that helper,
the input's `+4` field is required nonzero; it iterates a structure reached at
`[input+4]+0x34`, invokes direct helpers `0x002e81f0` and `0x0006df30`, and
conditionally grows/stores an 8-byte entry in fields reached from the ECX
object. This is a field-level mutation proof only: it does not justify naming
the data structure, relationship, or ownership policy.

The returned callback then makes two ordered pairs of registry raw lookups:

| pair | first reference source | second reference source | subsequent helper |
| --- | --- | --- | --- |
| 1 | upvalue `+0x20`, rawgeti `0x002ec1cc` | argument `+0x20`, rawgeti `0x002ec1d7` | `0x002ec1db -> 0x002ec050` |
| 2 | upvalue `+0x28`, rawgeti `0x002ec1ec` | argument `+0x28`, rawgeti `0x002ec1f7` | `0x002ec1fe -> 0x002ec050` |

Each `lua_rawgeti` uses `LUA_REGISTRYINDEX`; `0x002ec050` is a 180-byte Lua
stack procedure that iterates with `lua_next`, compares field names including
`__init` and `__finalize`, and performs table operations. This proves only the
direct static calls and raw-lookup inputs. It does not prove returned registry
values are tables, that the helper succeeds, or a complete Lua VM stack effect
through those helpers.

Finally `0x002ec203` through `0x002ec20a` write the argument userdata's first
word into the upvalue userdata's first word. The normal epilogue returns zero
Lua results (`xor eax,eax` at `0x002ec20c`), while the factory closure itself
was proven to return one result when created.

## Bounded initializer facts

The factory calls `0x002eacf0` on the 72-byte userdata. Its 612-byte atlas
body initializes multiple fixed offsets and creates several registry references
through `luaL_ref`; it also conditionally unrefs prior values and reads exact
registry keys including `__luabind_classes`, `__luabind_cast_graph`, and
`__luabind_class_id_map`. This is useful provenance for the fixed offsets used
by the returned callback, but this survey deliberately does not assign those
fields semantic names or prove their later validity.

## Candidate fail-closed artifact

An exact, narrow artifact could be named
`pe_native_lua_class_factory_callback_census`. It should join the four bound
artifacts and retain only this five-node chain: constructor, global publication,
factory callback, returned-closure construction, and returned callback. Its
records should publish normalized RVAs, atlas identities, instruction
size/SHA-256 facts, literal metadata/hashes, direct import identities, finite
CFG/entry audits, and declarative Lua-stack fragments.

Minimum exact checks:

1. Rebuild the `class` key/global-environment publication and target
   `0x002ec220` from the bound executable.
2. Require the factory's argument-count/type/nonnumeric/embedded-NUL branches,
   72-byte userdata allocation, initializer call, global-setter stack grammar,
   one-upvalue closure construction, and one-result terminal disposition.
3. Require the returned callback's `-10003` upvalue access, both
   `__luabind_classrep` helper checks, two rawgeti-pair sources, mutation site,
   and zero-result normal epilogue.
4. Require direct-call and IAT identities, register/stack argument adjacency,
   no alternate atlas entry into asserted dominated regions, and all
   prerequisite canonical digests.

Adversarial tests should separately change the key literal, destination index,
closure target/upvalue count, argument count/type checks, numeric-string
branch, NUL-length comparison, userdata size, initializer edge, settable index,
returned result count, upvalue pseudo-index, metatable-key literal, either
registry reference offset, rawgeti IAT, helper edge, mutation offset, or any
guard/CFG/prerequisite identity.

## Explicit nonclaims

This survey does not prove that `class` is globally available at runtime, that
the string is a source-level class name, that allocation or initialization
succeeds, that setters/raw getters have the intended values, that the two
userdata objects have any particular native type or relationship, that registry
references remain valid, that helper calls return normally, or that the chain
covers indirect/dynamic/Lua-level consumers and mutations.
