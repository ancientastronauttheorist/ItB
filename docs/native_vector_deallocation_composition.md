# Joined vector deallocation

The vector guard, two free thunks, free wrapper and guard return tail now
have a joined conditional contract. A separate exact replay executes all
159 bytes and 53 sites in one machine state. The guard's CALL and three
return-tail instructions are no longer external to this proof.

The guard retains its zero-stride and failure frontiers. Valid guards pass
their raw pointer to the free protocol. Null raw pointer returns through the
native null path; nonzero raw pointer follows the supplied HeapFree/error
protocol. The guard then removes its pushed argument, restores original EBP
and returns to its own caller. External API, accessor and mapper effects
remain supplied normal responses; no operating-system free executes.

## Fresh ancestor frame and storage checks

For guard entry ESP S, free entry is S-12 and its frame is S-16. The deepest
HeapFree CALL enters at S-32. Accessor and GetLastError enter at S-24;
mapper enters at S-28. The free wrapper returns at S-8, then guard cleanup
and return leave ESP=S+4. Original nonvolatile registers are restored.
Every completed path has all six final arithmetic flags from ADD(S-8,4),
overriding the free wrapper's flags.

The protected ancestor interval is [S-32,S+16), including the original
pointer, count and stride arguments. Metadata must avoid this interval,
modeled code, heap/global words and import slots. Error cells must also avoid
the metadata DWORD. These checks prevent a supplied error write from silently
changing an ancestor argument or the allocation metadata being preserved.

A numeric large guard can accept payload pointer 32 with raw metadata zero:
the distance is 32, and the free wrapper then takes its null path. EAX remains
32. Small raw-zero cases retain the guard's division quotient instead.
This is a machine relation, not evidence that raw zero names allocated storage.

## Evidence

The composition checks 304 contracts, 48 fresh return-tail cases, one rejected
cleanup mutation and four ancestor/metadata alias controls. The replay checks
992 cases: 512 normal returns and 480 guarded or free-protocol frontiers,
with 1,920 supplied external calls and zero opaque instructions.

The replay rebases the sealed independent guard and free oracles. It replaces
the standalone free oracle's caller-return event with the actual guard
continuation and checks fresh outer-tail equations. Complete stack, error,
global, IAT and metadata pages, ordered native accesses, general registers
and defined flags are compared. A supplied HeapFree response that corrupts
the outer stride is rejected by the complete-stack comparison.

Both independent reviews passed. All 34 focused tests passed, including
exact-executable CLI rebuilds. No actual free effect, provenance, division
fault execution, arbitrary external side effect or accounting promotion is
claimed.

## Reproduction

`scripts/itb_native_vector_deallocation_composition.py` accepts `--program-facts`,
`--guard-semantics` and `--free-protocol`. The joined conformance CLI accepts
`--composition`. Both provide `build`, `verify` and `verify-structure`;
exact commands require `--executable`, and verification requires `--evidence`.
Published prefix: `windows_build_13725832_31fe35265598_`.

- `native_vector_deallocation_composition.json`: canonical
  `1ac61cf845b48c512ceee4efa67a9a8585d3018b2a018bc8187297b7b264e2ba`;
  raw `c5a9139cfb82a7cb76ff9a3e09fc80796308527437a155ff5bb1600435266e55`.
- `native_vector_deallocation_conformance_joined.json`: canonical
  `8aba04f2be47f06284fbb3d00ebb7faa643613f99db3475fca54bd7f4cbc401a`;
  raw `c7f2f7abfc377f657554c973e1e05fc5ec64662bcb6a8eb7db046bcc25e86015`.
