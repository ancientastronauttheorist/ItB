# Into the Breach: solver-first plan

Date: 2026-10-02. Planning baseline: `87df785cf806b866319bac9c6baabe4a4662176e`.

## Outcome and authority

The project owner clarified the goal: **"the real goal for both is to make as perfect a solver as possible."** Both projects began with playing games and improving solvers; decompilation is a means of improving those solvers.

The outcome is an accurate, explicitly scoped rules model and a strong planner that can explain its recommendations and their limits. Recover original behavior where uncertainty limits model fidelity or decisions. A complete native game recreation, rendering stack, or byte-identical executable is not the solver acceptance gate.

This document is an additive solver-first priority plan. Preserve the existing decompilation evidence, proofs, tools and historical roadmap. It does not claim the old whole-program milestones are complete, change AGENTS.md, authorize live play, or resume the October 2 paused work. The user authorized this document's publication on `codex/full-decompile`.

Future GitHub publications must omit personal names, personal email addresses and identifying local paths, regardless of repository visibility. Check document content and commit metadata before publication.

## Existing foundation and first priority

- The Rust simulator/planner in `rust_solver/`, Python model and bridge, recorded boards, and failure cases are the starting implementation, not a replacement project. See [solver principles](solver_goal_principles.md) and [solver reference](agent/solver-reference.md).
- The [full-decompile program](full_decompile_program.md) separates L3 semantic recovery from later L5/L6 implementation/conformance. Its native movement and string proofs remain useful dependency evidence; their test totals are not whole-game solver coverage.
- The [October 2 handoff](decompile_handoff_2026_10_02.md) records bounded native comparison results and an unfinished alias-assignment frontier. Before another helper audit, reconcile the existing function ledger with reviewed evidence and connect one movement/effect scenario to the solver's observable result. Record which ownership, growth, string or scheduling dependency actually prevents that connection.

## Four independent claims

| Claim | Required evidence | Insufficient evidence |
| --- | --- | --- |
| Model fidelity | Legal actions and state/event transitions agree with the pinned original game on a declared domain | A self-consistent simulator or passing model-generated fixtures |
| Information legality | Every planner input is available to a player at that decision point, under the selected mode | A bridge field exists or can be read from memory |
| Search optimality | Complete enumeration or sound bounds certify the best action sequence for the declared objective, horizon and admitted model | Search timed out, a beam was exhausted, or no better plan was found |
| Practical strength | Held-out outcomes and latency/memory measurements under a fixed configuration improve or preserve the agreed objective | Raw test counts, commits, or an isolated winning run |

Within-turn exhaustive optimality is conditional on a correct transition model and complete legal-action generator. It is not a proof of campaign optimality. Future spawns, resistance, rewards and other uncertain outcomes require explicit branches or distributions; where these are unknown, report uncertainty rather than fabricate certainty.

## Build and evidence contract

Start with the documented Windows owner build: Steam app `590380`, build `13725832`, depot `590381 / 8335438558621014449`; x86 `Breach.exe` SHA-256 `31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`. The resource archive SHA-256 is `fd933aa7d13fe02a9ea577eb100c779f053734816e6c87abae863ae1c9efa4d5`.

This installation includes a Mod Loader overlay: it is not a pristine-depot claim. Pin the exact script/map/resource inventory, enabled content, bridge/mod version and configuration with every corpus version. Cross-build or cross-platform cases are separate until validated.

Every accepted rule links to the build, source/native address or script identity, evidence hash, input assumptions, original observation/trace, expected projection and known exclusions. Label evidence as original-game observation, bounded original-body execution, independently authored reference, or synthetic regression. Keep proprietary binaries/assets and raw private evidence outside public Git; retain manifests and lawful normalized facts for reproducibility. Exact JSON/report reproduction and native body identity do not prove a rebuilt executable is byte-identical.

## Information boundary and unresolved operating choices

Use an explicit player-observation schema: visible board, known units/weapons/upgrades, displayed enemy intents, public objectives and available action history. Audit each bridge field against that schema. Hidden RNG state/seed, unrevealed spawns, internal future decisions and privileged save/memory fields belong to a separate validation oracle, never implicitly to the planner.

Test pairs of oracle states with the same permitted observation/history: the planner must receive identical inputs and produce the same policy distribution under the same planner seed. Oracle outcomes may grade predictions afterward. A perfect-information diagnostic mode, if later requested, must be separately labeled and scored.

Open user choices: human-assist versus autonomous execution; target squads/content/difficulty; objective ordering; risk preference; tactical horizon; and acceptable latency/memory budgets. Neither mode is authorized to operate the live game by this plan. Proposed objective baseline is the existing lexicographic preservation policy (run survival, building/grid protection, valuable objectives, action economy, board control); achievement-specific overrides and campaign tradeoffs must be explicit configuration, not silent weight changes.

## Acceptance gates

All gates below are prospective; this document does not assert they currently pass. Scope the supported domain before measuring it. Zero unexplained mismatches is the acceptance condition for an **exact** supported-domain claim; excluded or unresolved cases stay in the denominator with reasons.

1. **Transition and legal-action fidelity.** Compare both the complete legal action set and resulting ordered events/state against original evidence. Cover move/attack/wait/end-turn, all controllable mission units, upgrades and targeting restrictions. Include damage, push chains/collisions, simultaneous and ordered deaths, terrain conversion, fire/acid/smoke/freeze/shield/armor/web interactions, building HP versus grid loss, enemy intent/order, environment timing, spawns/blocking and objective completion/failure. Include action-order permutations, move-before/after-use eligibility, swaps, friendly fire, zero/edge values and interactions rather than only isolated weapons. Unsupported actions must be reported, not silently dropped.
2. **State continuity.** Replay a complete player turn through enemy/environment/spawn resolution into the next decision state. Test mission termination, reset/undo and save/load where they affect available information or decisions, including RNG draw order and what undo restores. Normalize only irrelevant representation differences; never erase order or consumed state to obtain agreement.
3. **Independent differential corpus.** Freeze development and held-out partitions by scenario family, mission and acquisition provenance before tuning. Use original-game before/action/after traces and independent expected projections; keep self-generated fixtures in a separately labeled regression corpus. Include real failure cases plus controlled edge cases. Record attempted, admitted, rejected and mismatching cases by subsystem, with trace provenance. A held-out failure becomes a regression case only after retaining a fresh held-out replacement family; do not tune against the entire evaluation set.
4. **Determinism and uncertainty.** Fixed admitted state, action sequence, game build and recorded RNG stream must replay identically, including draw order. Planner randomness is separately seeded. If the original RNG state is unavailable to fair play, compare outcomes over the admitted distribution or possible outcomes, not a privileged predicted draw. Distribution comparisons require a predeclared tolerance/sample plan, not a post-hoc passing threshold.
5. **Search correctness.** On tractable boards, compare the planner with an independently implemented exhaustive enumerator: all legal action-order combinations, equivalent-state handling, terminal outcomes and optimal objective values must agree. Test pruning with adversarial building-saving sacrifices and mission units. Emit `proven_optimal` only with exhausted frontier or sound bound closure for the stated horizon; otherwise emit `best_found`, elapsed time, explored/pruned counts, remaining bound if valid, and unresolved uncertainty. "No clean plan found" must not become "no clean plan exists" without a certificate.
6. **Regression sensitivity.** Preserve discovered original-game mismatches as minimized cases. Deliberately perturb selected rules (push order, status priority, objective accounting, RNG consumption) and confirm the relevant checks fail. Test input parsing and observation filtering separately so extraction bugs cannot masquerade as rule errors. Model-to-model agreement alone cannot satisfy gate 1.
7. **Practical evaluation.** Compare a frozen solver baseline and candidate on the same held-out mission/campaign families, information policy and declared compute budget. Report objective-vector outcomes, illegal/unsupported actions, model divergences, wins/losses and causes, p50/p95/worst latency, nodes and peak memory, with uncertainty for stochastic outcomes. No numeric win-rate or latency target is agreed yet; proposed budgets and promotion thresholds must be selected before evaluation. Never trade correctness silently for speed.

## Milestones that deliver usable capability

| Milestone | Deliverable and acceptance |
| --- | --- |
| S0: reconcile and select | A reachable-gameplay coverage matrix, evidence links and one named movement/effect blocker. Reconcile ledger counts without automatically promoting every microproof. Freeze fair input schema and provisional objective/configuration. |
| S1: one faithful tactical loop | One representative movement/attack/effect scenario connected through player action and enemy/environment resolution, checked against original evidence and usable by the existing planner. Expose unsupported branches. |
| S2: certified bounded planner | A declared tractable squad/mission domain with complete legal actions and exhaustive-reference agreement. Return recommended sequences with model scope, objective and proof/budget status. |
| S3: mission breadth | Add prioritized weapon/status/terrain/objective families and full-mission continuations. Each increment closes named mismatches and passes independent held-out differential checks; ship capability rather than wait for every helper. |
| S4: uncertain campaign policy | Evaluate stochastic spawn/reward/economy decisions and longer horizons under fair information and selected risk preferences. Report empirical policy strength separately from any within-turn optimality certificate. |

Track reachable subsystems as rows: observation/legal actions, movement/effects, combat/status/terrain, enemy/environment/spawn sequence, mission objectives/termination, undo/save, and campaign economy/progression. For each row record admitted domain, original evidence, implemented transitions, search support, held-out result and blockers. Do not substitute native-function percentage for gameplay completeness.

## Work selection and progress reporting

Every reverse-engineering tranche starts with a solver-facing question, affected scenario, expected decision/fidelity improvement and exit test. Reuse reviewed allocation/string/runtime proofs where necessary; investigate additional helpers only when a named reachable behavior depends on them. UI/render/audio internals are deferred unless they block correct observations or legal action delivery.

Proposed stop rule: after one bounded tranche, if no new supported scenario, reproduced mismatch, removed uncertainty or necessary dependency closure is demonstrated, pause and reprioritize before continuing the helper chain. Repeated failed oracle acquisition or unchanged tests without a new hypothesis are also stop signals. Preserve useful results and explicitly record the blocked integration.

Each progress update should contain:

```text
Build / solver commit / corpus version / information mode / objective:
Named blocker and reachable scenario:
Before -> after supported behavior:
Original evidence and supplied boundaries:
Differential attempted / admitted / passed / failed / excluded by subsystem:
Search status: certified domain or best-found budget; valid bounds:
Held-out outcome and latency/memory versus frozen baseline:
New uncertainty, regressions and remaining exclusions:
Next end-to-end milestone; continue / stop / reprioritize rationale:
```

Counts of checks and native audits may support this report, but the primary progress measure is reliable decisions over more reachable gameplay with honest guarantees.
