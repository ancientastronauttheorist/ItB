# Centipede ordered-return correction (v410)

The solver now processes Centipede projectile side hits relative to the firing
direction. The previous fixed world-axis order reversed them for negative-x
and positive-y shots. This can change a simulated outcome: killing a Shell
Psion on the first side removes Armor before the second side is damaged.

The narrow change covers `CentipedeAtk1`, `CentipedeAtk2` and `CentipedeAtkB`
in the queued enemy projectile handler. It preserves other weapon families and
per-hit damage/status handling. It does not establish original death/aura
timing or close the complete tactical-loop gate.

## Original evidence and comparison boundary

[Normalized evidence](../data/solver_first/s1_centipede_order_evidence.json)
pins the August22 natural callback campaign receipt, its callback/source/content
joins, and all 18 artifacts from `get_skill_effect_pair002` and `pair003`.
The captured executable is Windows build13725832, SHA256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`,
5530112 bytes, with the owner modified overlay. The installed loader identity is
`0babc54e68539102b0c6b35e09307705736a2cdbb9dd4e0f36628a48fc497eb4`;
it differs from the later August29 capsule acquisition.

Event `seq=2`, callback `fn-0021` / `slot-0021`, returns the inherited
`CentipedeAtk1:GetSkillEffect` body for receiver `CentipedeAtk2`, actual
arguments `(4,2) -> (3,2)`, during `combat_enemy` in Mission_Power turn1.
The callback serializer joins the receiver to its runtime root. Its global
`Pawn` UID field does not independently identify the skill's owner.

| Ordered queued entry | Location | Damage | ACID | Push | Delay |
| --- | --- | --- | --- | --- | --- |
| Main projectile | `(3,2)` | 2 | 1 | 4 (none) | -2 |
| First side | `(3,1)` | 2 | 1 | 4 (none) | 0 |
| Second side | `(3,3)` | 2 | 1 | 4 (none) | 0 |

All 25 serialized fields of each queued entry are preserved in the normalized
facts. Immediate `effect` is empty. Each pair contains 48 repeated Centipede
calls with one argument pair and one primitive summary. The second pair repeats
the entire event stream: SHA256
`256a92540532e7f14e4968ed0ac8d5c34d481215bbde63ada399aacd8b01d7e5`.
Thus 96 observed returns contribute **one** distinct returned-effect scenario.
The complete trace records 146 accepted events from 147 attempted calls per
pair; the dropped call is retained in the accounting.

The pinned shipped `scripts/weapons_enemy.lua` body at lines325-345 specifies
main, first relative side, second relative side. Its SHA256 is
`5231dd7a2de730f04fa4116c0d99f07ecbb3b25059db3593d54d689c37bd4b7b`.
The alpha inherits it; the separately pinned Boss body at
`scripts/advanced/bosses/centipede.lua:59` uses the same flank order. Native
direction/vector anchors and `scripts/global.lua:17` establish the Lua winding.
For cardinal displacement `(dx,dy)`, the ordered side offsets are
`(-dy,dx)` then `(dy,-dx)`. Rust's `DIRS` winding is opposite, so directly
substituting its `dir+1` would reverse this law.

This is an **original returned queue**, with a broader source-derived cardinal
law. Neither pair retains a complete before board or identifies which returned
queue the native executor selected. Their control and hooked later outcomes
differ on two spawn-coordinate fields. Consequently this is not an observer
neutrality claim, a full state-transition admission, or proof that the synthetic
Psion outcome below occurred in the original game.

The dispatch follow-up narrows the missing link: existing forward traversal
evidence concerns the immediate `effect` vector, not `q_effect`. The generic
cache/enqueue/dispatcher chain does not associate this returned Centipede queue
with its selected executable batch. A one-record Firefly materialization cannot
prove multi-record Centipede dispatch order. The private association review is
retained with SHA256
`1149bda2df3ea37299792fdbab50a810be7ab646cde064954491edd5ed2c83ea`;
execution and endpoint admissions remain zero.

## Regression and remaining scope

The synthetic Rust test places a Shell Psion on the source-defined first side,
an armored Vek on the second side, and a player target at impact. It checks all
three Centipede families in all four cardinal directions. The old code fails
the negative-x normal Centipede case: the second victim remains at HP5 instead
of HP4 because it is hit before Armor removal. The corrected code passes the
12 subcases. Existing Centipede damage, status, water, edge and Boss-path tests
also pass. This demonstrates sensitivity and fixes Rust's order; original
damage/aura execution remains a separate validation requirement.

The evidence tests verify all 23 retained receipt/join/artifact/native-vector pins, reproduce
the original eventstream and primitive-summary hashes, compare all queued
fields, and detect side-order, damage and ACID perturbations. They do not run the
game or substitute simulator output for original evidence.

Both simulator pins advance from409 to410. The tracked pre-change failure DB is
archived as `recordings/failure_db_snapshot_sim_v409.jsonl`, SHA256
`a5bf0a9b459e754a3bf9c49b5564c745687273aa04fafddd60e82d9de43f0b66`,
5759697 bytes. Pre-existing local records remain protected. No objective,
information policy or planner search rule changes.

Validation: nine focused Centipede Rust tests and all 1017 release Rust unit
tests pass. Forty focused Python checks pass across the new evidence comparison,
archived projection grader, S0 information boundary and strict refresh budget.
The release extension is rebuilt, installed, and reports simulator410 matching
the Python pin. The full recorded-board regression passes all 1052 tracked
boards, including 303 requiring actions, with zero unexpected failures; its
five admission checks also pass (six Rust integration tests total, 359.73s).
These are crash, required-action and bounds regressions, not original-game
transition equivalence or held-out wins.

The existing Python failure-corpus harness also passes in82.25s: 339 filtered
records, zero unexpected triggers, one known issue, 132 missing-board skips and
146 empty solver responses. Sixty produced plans have no flagged trigger;
the remaining produced plan retains the known issue. These are self-consistency
checks, not 60 newly fixed bugs. Its legacy empty-response guard uses old team
IDs, so it cannot certify current canonical actor readiness; the Rust parsed
board admission above separately checks that requirement. No skipped or empty
case is promoted into original transition coverage. All 13 pre-existing local
file hashes remain unchanged through validation.

Open branches include the Boss's path ACID being applied before flanks in Rust,
where shipped source appends it afterward; player projectile side-splash
coverage; other perpendicular families; selected native queue attribution;
original death/aura scheduling; and fair loadout/intent/next-decision provenance.
These remain exclusions rather than passing cases. All related acquisitions
are development, with no held-out, search-certificate or practical-strength
claim.

## Tranche progress report

| Required dimension | Checkpoint |
| --- | --- |
| Build / solver / corpus / information / objective | Windows13725832 owner modified; baseline `0cfa940548dab649b7a2742c26a160cf1a2bbe0a` v409; candidate v410; `s1-centipede-ordered-return-development-v1`; offline original-return facts and separately synthetic regressions; unchanged preservation policy |
| Named blocker and scenario | Does queued Centipede flank ordering agree with the original returned effect, and can the discrepancy affect solver outcomes? |
| Before -> after | Fixed-axis reversal -> direction-relative flank processing for three weapons; synthetic Psion sensitivity case now follows the returned order |
| Original evidence and supplied boundaries | Two sealed original callback traces, one distinct return scenario; no complete before board or selected native execution; synthetic board explicitly supplied |
| Attempted / admitted / passed / failed / excluded | 96 Centipede returns, one distinct returned-effect scenario; all 75 queued fields checked; twelve synthetic directional subcases; zero full execution-transition, fair-input or legal-action-set admissions |
| Search and bounds | No search certificate or new valid bound; solver search remains best-found |
| Held-out outcomes / latency / memory | No held-out practical comparison; budgets/promotion choices still unresolved |
| Uncertainty and regressions | Original queue discrepancy retained and corrected in Rust; original execution/aura timing, Boss trail order, fair input acquisition and full-cycle continuity remain open |
| Next milestone / rationale | Connect an original selected queued effect to its actual intermediate/after board. Continue because this tranche reproduces a source-backed ordering discrepancy with a discriminating regression, rather than extending an unrelated helper chain |
