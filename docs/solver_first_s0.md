# Solver-first S0 checkpoint

This checkpoint implements the first work-selection step in
[the solver-first plan](SOLVER_FIRST_PLAN.md). It reconciles retained movement
evidence, freezes a provisional offline information contract, and connects a
native path-rule inference to the current Rust replay interface. S1 through
S4 and the seven acceptance gates remain open.

The later [S1 query comparison](solver_first_path_query_conformance.md) supplies
bounded original vectors, corrects historical team-prefix labels, and advances
the simulator to v409. The v408 S0 report below remains a historical synthetic
checkpoint with its own pinned implementation.

## Build, solver and information mode

- Original executable: Windows build `13725832`, depot
  `590381 / 8335438558621014449`, SHA-256
  `31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`.
- Solver source baseline: `fda5572aa242833e3875fb56d5bd19c551a43b70`,
  simulator version 408, rebuilt and installed for Python 3.13 on Windows.
  The report records the implementing extension hash and normalized Rust
  source hashes. No Rust semantics or version pins changed in this tranche.
  New JSON artifacts and the entry point have explicit Git line-ending rules;
  frontend dependency hashes use named LF normalization.
- Corpus: `s0-water-development-v2`; every new scenario is synthetic development
  evidence. There is no held-out partition or original runtime trace in it.
- Information: `provisional_player_observation_v1`. The
  [contract](../data/solver_first/s0_information_contract.json) accounts for
  all 43 top-level parser fields, 24 tile fields, and 49 unit wire names
  including the `is_grappled` alias. Nested mission payloads remain quarantined
  as whole fields until their value provenance is audited.
- Objective: existing [lexicographic preservation policy](solver_goal_principles.md),
  with no new weights or achievement overrides. The ten-second search budget
  is a provisional existing default, not a practical promotion threshold.
  The replay check does not consume a search budget; the trivial policy-equality
  test uses one second. Squad/content/difficulty, risk preference, campaign
  horizon and quantitative promotion criteria still need selection.

The adapter is experimental and used only by offline evaluation. It rejects
unknown, pending, or state-supplied configuration fields instead of silently
losing model-critical inputs. Known oracle fields such as unrevealed remaining
spawn counts and RNG state are withheld. It replaces private engine UIDs with
labels ordered by visible position/type, remaps displayed attack order,
normalizes tile order and the grappled alias, and rejects duplicate identities.
Filtering keys does not establish acquisition legality: admitted values still
require visible UI/action-history or pinned public-definition provenance.
The live bridge and normal planner are not routed through this adapter yet.

## Ledger reconciliation

The existing authoritative accounting verifier re-read the exact executable
atlas and reproduced the retained ledger. The registry has zero claims:
25,312 functions remain L0; L1, L2, reviewed functions and exclusions are zero.
Atlas discovery includes 25,490 ranges and 3,735,718 unique body bytes, with
86,498 declared direct-call records and 18,477 omitted targets. Discovery-byte
coverage does not measure semantic or gameplay completeness.

The [movement evidence index](../data/solver_first/s0_movement_evidence_index.json)
links eight retained conformance receipts and the static binding receipt to
their canonical identities and bounded scopes. Their sums are 576 cases and
502 negative controls across overlapping experiments. Four binding bodies,
20 normal AddMove bodies, and 21 normal AddCharge bodies match atlas entries,
body sizes and hashes. The index makes zero review-level promotions.

The seven latest laws in the [October 2 handoff](decompile_handoff_2026_10_02.md)
retain models, independent tests and prose-reported native probes; they do not
have corresponding newly sealed corpus receipts under `programs/`. All seven
model hashes match Git LF blobs. Three test hashes in the handoff refer to
Windows checkout CRLF bytes, while four refer to Git LF bytes. These conventions
must be named when comparing hashes; the difference is not semantic drift.
Existing atlas accounting has five native/Lua census adapters and no automatic
movement-conformance promotion adapter. Ownership, exact whole-function
boundaries and complete immediate reference sets remain separate requirements.

## Reachable-gameplay coverage matrix

This matrix describes the current evidence boundary, not a complete-game claim.
Only the S0 Water corridor has new measured results here. Other rows retain
existing implementations/evidence and unmeasured gaps; they are not admitted
as exact supported domains by this checkpoint.

| Subsystem | Existing implementation and original evidence | New measured domain/search support | Held-out result and blocker |
| --- | --- | --- | --- |
| Observation/legal actions | Python bridge/model; Rust JSON parser; native path registration/profile maps | All current parser wire fields classified provisionally; equal-oracle-input tests; corridor replay acceptance across all destinations | No held-out result. Broader value acquisition and full legal attack sets need original comparisons; live integration remains pending. |
| Movement/effects | Rust movement/simulation; exact-build path cost/occupancy maps; bounded AddMove/AddCharge construction receipts | Ground/profile-2 Water corridor, budgets 1/2; 189 distinct destinations agree with static-rule expectations; three separate Rust no-op checks | No original output vector or held-out result. Origin publication, movement record consumption, per-step effects, interruption and scheduler ordering remain open. |
| Combat/status/terrain | Rust weapon/simulation modules, recorded failures, shipped-script and native mechanic evidence | Existing planner capability retained; no new admission or measurement | Independent interaction corpus and ordered original outcomes remain required. Synthetic regressions alone do not establish fidelity. |
| Enemy/environment/spawn sequence | Rust enemy/turn projection, Observatory callback/materialization/spawn receipts | Existing tactical replay retained; original receipts remain bounded to their declared subjects | Full ordered player-to-next-decision trace missing for this scenario; future spawn and intent uncertainty must remain explicit. |
| Mission objectives/termination | Rust objective accounting and mission metadata; existing terminal-flow evidence | Existing capability retained; no new measurement | Need mission-family admission and independent objective/terminal outcome comparisons. |
| Undo/save | Existing bridge/save parsing and native boundary evidence | No new admission or search certificate | Information availability, undo restoration and RNG draw order need matched original before/after evidence. |
| Campaign economy/progression | Existing strategy modules and achievement-run records | No new admission or quantitative evaluation | Freeze fair-information campaign configuration, risk/budget and promotion thresholds before held-out evaluation. |

## Named scenario and blocker

Question: can the existing solver recognize a Massive unit's legal Water stop
and route to a tile beyond Water, without consuming hidden future information?

The controlled corridor is visual **H8 -> G8 -> F8 -> E8** (bridge `(0,0)`
through `(0,3)`); G8 is Water and all off-corridor tiles are Mountains. The
handwritten expected distinct destination sets are empty for a nonmassive ground
profile, G8 for Massive budget one, and G8/F8 for Massive budget two. Each
variant also checks a separate Rust no-op request at H8. Original GetReachable
publication of the occupied origin remains unresolved; accepting a Rust no-op
does not establish that the original query returns H8. The nonmassive
`CombatMech` variant is a synthetic profile override, not an original-game pawn
configuration claimed reachable. Each variant tests all 64 destination requests.

Before this tranche, the Water rule, Rust movement regression, and native
record-construction proofs were separate artifacts. After it, the offline
tool re-verifies exact original executable path evidence, passes the declared
information boundary, and observes actual Rust replay legality/position for
189 distinct destination requests and three Rust no-op requests, with zero
mismatches. This is a source-rule-to-solver
connection; it is not a newly corrected simulator rule or original gameplay
transition proof. Water/profile interpretation remains the reviewed source
inference documented in the native map and
[native anchor research](itb_native_anchor_research.md#native-path-cost-and-ordering-boundary).

The [report](../data/solver_first/s0_water_rule_report.json) labels the evidence
distinct-destination static-rule inference and Rust no-op contract separately,
with zero matched original runtime comparisons and no search/held-out result. Original before,
action, ordered events and after-state comparison remains the S1 exit test.
The exact current script/map/overlay inventory must be pinned for that loop;
this executable-only check consumes no runtime resource overlay.

The next solver-facing blocker is matched original GetReachable output and the
AddMove consumer/effect scheduler for the declared route. Alias-string
assignment, growth or allocation work is justified only if that concrete route
requires it. Existing empty-inline, short-path, successful-allocation proofs
should be reused. Another isolated string helper closure would not close S1.
The [S1 acquisition frontier](solver_first_s1_frontier.md) records the exact
query/consumer boundaries and the required original output comparisons.

## Reproduction and acceptance status

From the repository root, supply the owner's local executable path and new
output paths (publication is create-only):

```text
python scripts/solver_first_s0.py --executable <owner-local-executable> --output <new-report.json> --movement-index-output <new-index.json>
python -m pytest -p no:faulthandler tests/test_solver_first_s0.py tests/test_observatory_path_cost_ordering.py -q
```

The tool re-verifies the path map and existing whole-function ledger against
the original executable, checks every parser field has a classification,
reconciles receipt/atlas membership and performs the 192 Rust projections.
It reports three hidden-oracle observation pairs with identical planner input.
This tranche also rebuilt/installed the extension and ran the focused Rust
movement tests. Source-only independent review identified extension-resolution
and tile-canonicalization issues, both corrected before final validation.

| Gate | Current S0 evidence | Status |
| --- | --- | --- |
| 1: fidelity | Reverified original static path rules and synthetic replay agreement; no original output vectors or ordered full action trace | Open |
| 2: continuity | Replay interface exercised, but no original player/enemy/environment/spawn/next-state trace | Open |
| 3: differential corpus | Explicitly labeled development corpus; no frozen independent held-out acquisition | Open |
| 4: determinism/uncertainty | Oracle-input invariance checked; full original RNG replay/distribution plan absent | Open |
| 5: search correctness | Trivial equality check only; no independent exhaustive enumerator or optimality certificate | Open |
| 6: sensitivity | Boundary rejection and negative Water/budget controls; broader rule mutations/minimized original mismatches pending | Open |
| 7: practical strength | No held-out outcomes, campaign measures or latency/memory promotion comparison | Open |

Continue toward S1: this tranche supplies a concrete scenario, executable
evidence links, measured solver projection and an explicit information boundary.
It does not complete the solver-first goal or revive live game operation.
