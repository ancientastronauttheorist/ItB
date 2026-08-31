# Native Lua `super` rebinding survey

Status: read-only static research checkpoint. This note follows the three
proved native publications under exact global key `super`. It does not
reconstruct source or prove runtime reachability.

## Bound evidence

The scope is the x86 Windows `Breach.exe`, build `13725832`, SHA-256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
All addresses below are image-relative RVAs. The chain composes:

- program-facts atlas canonical SHA-256
  `631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803`;
- direct Lua import-call census canonical SHA-256
  `07ed5edabe6fba37a89dd9542f197e75e58e1a2b064b5940e424847b1f843608`;
  and
- table-key provenance census canonical SHA-256
  `8b8cab571c3c8945dae440933107022b35eed28b4c806a35188202bd52073db6`.

Every publication uses literal `super` at RVA `0x0043bfa0`, five bytes
excluding NUL, with NUL-inclusive SHA-256
`d4d1c249a1a435e59c999c3e262163b1022292c314e450419e8edf29fc79e024`.
The literal is in non-writable `.rdata`. Every destination is
`LUA_GLOBALSINDEX == -10002` and every setter is `lua_settable`; these are
metamethod-capable assignment requests, not raw or durable global-state proof.

## Exact three-publication chain

| role | caller | closure call | callback | setter |
| --- | --- | --- | --- | --- |
| bootstrap error callback | `0x002e6900` | `0x002e6c01` | `0x002e6810`, zero upvalues | `0x002e6c10` |
| guarded dynamic replacement | `0x002eb020` | `0x002eb086` | `0x002eb230`, two upvalues | `0x002eb092` |
| callback self-replacement | `0x002eb230` | `0x002eb2a5` | `0x002eb230`, two upvalues | `0x002eb2b1` |

The first site has Lua stack trace `K -> K,C -> consume K,C`. The other two
construct `K,U1,U2 -> K,C -> consume K,C`. Their shared key and destination
connect the static assignment requests; they do not prove the order in which
any Lua state observes them.

## Bootstrap error callback (`0x002e6810`)

This callback is a 33-byte atlas body with SHA-256
`b2047ad08a7ffc19a210f5001f66ba53c9c1f6e8674e7af0cd51b661fd66f82e`.
It reads no arguments or upvalues. It pushes the exact 181-byte literal at RVA
`0x0043be60` and calls `lua_error` at `0x002e6824`:

```text
DEPRECATION: 'super' has been deprecated in favor of directly calling the base class __init() function. This error can be disabled by calling 'luabind::disable_super_deprecation()'.
```

The literal's NUL-inclusive SHA-256 is
`d3f573ecb939aff704f2a7399593c472ecfd189eff5cce8c646ccdeebded29c6`.
Under the Lua 5.1 non-returning `lua_error` premise this callback always errors;
its binary fallback returns zero only if `lua_error` unexpectedly returns.

## Guarded dynamic replacement (`0x002eb020`)

The 273-byte body has SHA-256
`cce4ab6d208cbdcbe5316c73acc1ecc3f621e931d349cd759889d8c5aced0e1b`.
Its publication arm is guarded by the byte at RVA `0x004b9e9f`, argument-1
userdata field `+0x2c == 1`, and unequal `+4`/`+8` fields in a reached object.
These are field and branch facts, not semantic flag or type names.

Helper `0x002ea430` leaves a new 48-byte userdata `Unew` above the original
arguments. It writes the argument-1 userdata pointer at `Unew+0x28`, writes
zero at `Unew+0x2c`, and applies environment/metatable operations using
argument-1 reference fields `+0x20` and `+0x30`. The publication sequence then
pushes:

```text
[A1..An,Unew] -> [A1..An,Unew,K,A1,Unew]
              -> [A1..An,Unew,K,C]
```

`lua_pushvalue(L,1)` supplies closure upvalue 1 and
`lua_pushvalue(L,-3)` supplies upvalue 2. The latter index denotes `Unew` at
that exact stack point, not a source-level variable inferred from proximity.

After the assignment request, the function reaches a registry lookup from
argument-1 field `+0x20`, indexes exact literal `__init` at RVA `0x00420f68`,
and calls `lua_call` at `0x002eb0f1` with the saved initial stack count as its
argument count and zero results. The `__init` literal is six bytes excluding
NUL and has NUL-inclusive SHA-256
`bbd60ce6705e249e0cffaa2e7e02fb2a3915650144e2faba59b0188a89895185`.
On the flag-enabled normal continuation it requests `globals.super = nil` at
`0x002eb103` through `0x002eb11c`. Its binary normal return count is one, but a
complete returned-value identity is not proved here.

## Self-replacement callback (`0x002eb230`)

This callback is a 263-byte atlas body with SHA-256
`55323a8ca497f78c3e6e1bfe995113b3071c6a164d239df4cc6b045a63be6e98`.
It obtains upvalue 1 with
`lua_touserdata(L, lua_upvalueindex(1))` at `0x002eb241` through
`0x002eb24a`, follows two fixed `+4` fields to `ESI`, and compares fields
`[ESI+4]` and `[ESI+8]`.

If those fields differ, the callback builds another two-upvalue closure
targeting itself. Its new upvalue 1 is `lua_pushlightuserdata(ESI)` and its
new upvalue 2 is the preserved current `lua_upvalueindex(2) == -10004` value.
It then requests another assignment under global key `super`. If the fields
are equal, the alternate arm instead requests `globals.super = nil` at
`0x002eb26d` through `0x002eb27c`.

Both arms continue through `lua_rawgeti` with registry reference `[ESI+0x20]`,
index `__init`, insert that value at stack index 1, copy current upvalue 2 and
insert it at index 2, then call `lua_call` at `0x002eb307` with saved initial
argument count plus one and zero results. On normal return from that call, the
callback unconditionally requests `globals.super = nil` at `0x002eb310`
through `0x002eb325` and returns zero.

This is exact pointer-walk, closure-capture, call-arity, and cleanup control
flow. Naming it a source-level base-constructor mechanism would go beyond the
static proof, even though the exact error and `__init` literals motivate that
hypothesis.

## Complete direct target-reference boundary

A second independent Capstone scan of every exact atlas function range found
exactly three immediate or memory operands equal to either callback VA:

| instruction RVA | target RVA | use |
| --- | --- | --- |
| `0x002e6bfb` | `0x002e6810` | bootstrap closure producer |
| `0x002eb080` | `0x002eb230` | guarded two-upvalue producer |
| `0x002eb29f` | `0x002eb230` | self-replacement producer |

There are zero direct calls, comparisons, or other address uses in this finite
operand-equality partition. This does not exclude computed or indirect
function pointers, data references, un-atlased code, or Lua-side invocation.

## Candidate fail-closed artifact

A normalized `pe_native_lua_super_rebinding_chain` artifact should retain the
three prerequisite-bound publication rows, literal and callback body
identities, guard CFG, helper stack delta, exact upvalue derivations,
publication/alternate-clear/post-call-clear paths, `lua_call` arities and
normal return counts, and the three-item target-reference partition.

Adversarial tests should independently mutate each key, callback, setter,
upvalue source/index, guard edge, helper-created userdata stack position,
`__init` identity, call arity, cleanup edge, body hash, operand partition, and
prerequisite digest. A PE-free validator may replay normalized facts, but the
artifact builder must re-decode and re-read the exact executable.

## Explicit nonclaims

This survey does not prove runtime reachability or frequency, the meaning of
the guard byte or native fields, concrete C++ types or ownership, valid
registry references or table types, successful `lua_call`, cleanup after a
Lua error or long jump, raw/stable global state, absence of metamethod effects
or reentrancy, exclusivity against dynamic Lua publications, Lua-side
consumers, or source equivalence.
