# Callback upvalue validation boundary model

`native_lua_class_callback_assertion_prefix_semantics.apply` describes two
conditional callback failures before the native assertion helper executes.
It accepts a nonzero uint32 state and a uint32 supplied upvalue userdata word.
Zero userdata ends the Lua request sequence after touserdata at index -10003;
later marker inputs remain opaque. Nonzero userdata requires an exact boolean
metatable contract and a nil or false marker, with nil required if absent.

The nonzero family requests the native marker's compatible Lua calls: obtain
the upvalue metatable, then, if present, push the marker key, gettable at -2,
convert the nil or false result to zero at -1, and restore the original stack
with settop(-3). The original argument remains intact. The logical marker AL
is zero; the model assigns no full-EAX word or imported DLL behavior. Calls
record detached before/after token stacks, signed logical indices and supplied
results. Void results use zero comparison placeholders.

The null family requests native target RVA `0x00379cc2` with words
`[0x0083ca00,0x0083c9c8,69]`, returning syntactically to VA `0x006ec151`.
The false-marker family requests the same target with
`[0x0083c908,0x0083c9c8,70]` and continuation VA `0x006ec175`. These are
offset-level pointer and scalar facts; no meaning or contents of the pointed
expression or filename are inferred. With entry ESP S and frame F=S-4, both
boundary frames have ESP F-52 and four words `[continuation,argument1,argument2,
argument3]`. The continuation is a machine CALL word, not a claimed return.

No assertion-helper response is supplied. Assertion delivery, recovery,
unwinding, callback return, security-cookie verification, Lua VM effects,
source ownership and successful argument processing remain outside the model.
Independent tests cover short-circuit opacity, false Lua values and stack
restoration, strict reached word/kind domains, exact frames and output
detachment. The separate native proof checks actual instruction execution.
