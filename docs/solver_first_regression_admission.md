# Python recorded-board regression admission

The Python failure-corpus harness now rejects empty, non-timeout results on
canonically parsed active boards. The old wire-team-0/team-1 guard missed the
actual player-team-1/enemy-team-6 case. An injected empty native result made the
new sensitivity test fail against the old guard and pass against the repair:
the old harness reported zero unexpected regressions; the new harness rejected
that same injected result. This is a reproduced harness defect, rather than a
solver transition change.

[The frozen validation report](../data/solver_first/regression_admission_412.json)
pins source, configuration, protected local failure-database, filtered corpus,
existing recorded boards and loaded extension identities. The baseline is
`96e497206def812904e6a4370a672c1c43c695e9`. Simulator version remains 412:
the new Rust `inspect_admission` API only parses and reports actor/enemy
admission. It changes neither simulator transitions nor search policy.
The rebuilt installed release extension SHA256 is
`d6e9190bb194e5a9de7179a25f83d35b9d63c5727be1c2ce399701b78febbe40`.
The earlier [primitive comparison](solver_first_primitive_search.md) remains
historical evidence from a distinct v412 build; its frozen report is unchanged.

The regression wrapper captures exactly the prepared JSON passed by the
production `_solve_with_rust` helper. Rust parses that same input and applies
`active_mechs()` and living `enemies()`. This retains parser defaults, armed
mission allies, movable VIP Trucks, and burrowed enemies without reconstructing
the predicate from wire teams or a lossy serialized board. The production
helper remains untouched, including existing user changes.

The helper discards native score/timeout metadata when it returns an empty
`Solution()`. The harness preserves the native result before that loss. Required
empty results pass only with a finite numeric native score and explicit boolean
`stats.timed_out=true`; absent/nonfinite scores and malformed timeout receipts
fail. `accepted_empty_timeout` counts only results accepted by that policy,
rather than all native timeout flags. Actor admission does not prove a legal
action exists. Active boards without living enemies remain outside this
required-empty policy, including possible environment/spawn/objective work.

All 26 focused checks pass, including the injected fault, canonical teams,
defaults, mission allies, unsupported actors, frozen actor admission, burrowed
enemies and wrapper metadata loss. The final full-corpus run passes in 75.65
seconds at the existing two-second per-case search budget:

| Classification | Count |
| --- | ---: |
| Filtered records | 339 |
| Existing recorded boards | 207 |
| Missing recorded boards | 132 |
| Absent replay references / load errors | 0 / 0 |
| Successfully returned solves classified action-required | 61 |
| Empty solutions / required empty solutions | 146 / 0 |
| Accepted required empty timeouts | 0 |
| Harness classified fixed / known self-consistency issue | 60 / 1 |
| Unexpected regressions | 0 |

The 146 empty exempt cases and 132 missing boards are not successful original
failure reproductions. The 60 fixed classifications mean no selected
self-consistency trigger fired; they do not establish agreement with an
original outcome. Corpus augmentation remains historical replay input rather
than admitted fair player information. No loaded existing board was turn zero
or missing its turn, so the production helper's local-save mine fallback was
not reached by these cases. That fallback remains an explicit future provenance
limit. The protected local failure database and private board inventory are
hashed but not published or modified.

Original evidence for the separate [stored-readiness setter](solver_first_readiness_leaf.md)
adds six bounded original-body projections, with zero full gameplay transition
admissions. This Python guard adds regression sensitivity, with no search
certificate or valid bound, independent original differential corpus, held-out
outcome/latency/memory comparison, or gate promotion. All seven goal gates and
the full S1 tactical cycle remain open.

Continue: a named admission failure is now reproducible and detected. The next
S1 exit test remains original action/ordered immediate result/next decision
continuity with frozen content and information provenance. The next S2 increment
still requires independent target completeness and broader bounded enumeration.
Reproduce the guard checks in serial, with `PYTHONFAULTHANDLER` removed:

```text
python -m pytest -p no:faulthandler tests/test_regression_admission.py -q
python -m pytest -p no:faulthandler tests/test_regression_corpus.py -q -m regression -s
```
