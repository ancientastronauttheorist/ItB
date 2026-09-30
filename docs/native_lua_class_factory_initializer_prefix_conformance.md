# Continuous factory and initializer prefix

This exact-build finite proof extends the
[normal factory prefix](native_lua_class_factory_prefix_conformance.md) through
the first 37 instructions of initializer RVA `0x002eacf0`. It stops at helper
entry `0x0007c600`, before any helper instruction executes. All native code runs
in one x86 Unicorn machine; only the same seven Lua API responses are supplied.

The executable SHA is
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
Four source receipts are pinned: program facts, factory chain, initializer
chain and the sealed factory prefix. The 612-byte initializer owner has SHA
`b681567bb998cd2c86267435483c7763394bd4df7843dcd8be7ecfb9e326d712`.
Its selected 160-byte prefix has SHA
`bc354d047d85c42203b24717d802ed07790d4ca97ee922544c25a2b231740fda`.

The corpus preserves all 216 factory cases: six NUL lengths, three byte
patterns, three alignments, two pointer relations and two caller profiles.
Factory entry flows directly into the initializer using the actual current
pages, registers, original argument words and active FS chain. There is no
synthetic initializer return or substituted native helper behavior.

The [independent initializer model](native_lua_class_initializer_prefix_semantics.md)
specifies 14 ordered word writes. The second tolstring pointer is stored at
userdata offset 16. Offsets 48, 60, 64 and 68 remain untouched, with their
original bytes preserved. Literal offset-zero data and the zero or sentinel
values receive no source-level ownership, type or registry interpretation.

Let factory entry ESP be `S`, factory frame `F=S-4`, initializer entry ESP
`N=F-48` and initializer frame `G=N-4`. Its helper-entry ESP is `G-36`, holding
return VA `0x006ead90`. FS:[0] is `G-12`; that cell preserves the factory's
active chain `F-12`, whose cell preserves the original incoming chain.
The cookie setup word is `cookie XOR G` at `G-32`. The initializer reads the
second argument at `G+12`, then overwrites that slot with `userdata+52`.

At the endpoint, EAX is the second string pointer, ECX=EDI=userdata,
ESI=userdata+52, EBP=G and ESP=G-36. EBX retains the staged pushstring binding;
EDX retains the supplied volatile word from newuserdata. The latest native
flag-setting instruction is the cookie XOR, checked under mask `0x8c5` with
undefined AF excluded. Neither cookie verification nor exception handling
executes before this boundary.

The independent oracle reconstructs all ordered memory events, full mapped
pages and final registers. Every one of 108 normal sites executes: 71 factory
sites plus 37 initializer sites. The 12 factory error sites remain excluded.
Selected code totals 391 bytes. The corpus executes 64,944 native instructions,
including 7,992 initializer instructions, and supplies 1,512 API calls.

All 22 controls check their specified rejection reason. Seven added controls
cover the stored name pointer, sentinel field, untouched field, outer and
inner FS cells, overwritten argument slot and helper continuation. The
original 15 factory controls remain active. At this new endpoint, the inherited
control named `handoff_pointer` mutates ESP+8, the saved incoming EDI word at
G-28 containing P2. It checks preservation of that saved word; the added name
field and overwritten-argument controls check current pointer propagation.
The default factory runtime and
its earlier sealed receipt remain separately verified after adding the
private continuation machinery.

Receipt:
`data/observatory/programs/windows_build_13725832_31fe35265598_native_lua_class_factory_initializer_prefix_conformance.json`.
Canonical SHA:
`abd888a364076edd037f460a0515b9586610218f9e5437aa4f67ab0cd972c47e`.
File SHA:
`9f64ec4a0124e1ad7f52cda34c7faaa949e924484df55e9a8f40c24ab23e827f`.
CLI commands build, verify and verify-structure require all four source
receipts. Exact execution and tests run in isolated subprocesses.

The later [record construction proof](native_lua_class_factory_record_conformance.md)
executes the helper and native allocation wrappers, then checks its actual
returned pointer store at userdata offset 52. This prefix receipt retains
its original endpoint and byte identity.

This proof excludes self-linked helper execution, allocation machinery, later
initializer Lua calls, both returns, remaining factory instructions, real Lua
VM behavior, heap ownership, exceptions, error paths, arbitrary memory domains
and program-wide accounting promotion.
