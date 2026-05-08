---
id: 20260508_134925_472_m02_t02_mech_damage_unexpected
failure_id: 20260508_134925_472_m02_t02_mech_damage_unexpected
run_id: 20260508_134925_472
mission: 2
turn: 2
action_index: null
sim_version_at_diagnosis: 67
status: needs_agent
confidence: low
applied_in_commit: null
retired_in_sim_version: null
duplicates_of: null
target_language: rust
proposed_files:
  []
rules_matched:
  []
agent_invoked: false
agent_tokens: 0
diff_signatures:
  []
---
## Symptom

Unit diffs:
  (none)

Tile diffs:
  (none)

Scalar diffs:
  (none)

## Hypothesis

No seeded rule matched this diff signature. The Layer 2 agent fallback prompt is below — dispatch it via the harness's Agent tool, then pipe the JSON response back through `game_loop.py diagnose_apply_agent <failure_id> '<json>'`.

## Proposed fix

(none — needs agent)

## Verification plan

- `bash scripts/regression.sh` (Rust + Python corpus)

## Agent prompt

Dispatch this prompt via the harness's Explore agent. 
When the agent returns its JSON, run `python3 game_loop.py diagnose_apply_agent 20260508_134925_472_m02_t02_mech_damage_unexpected '<json>'` to validate + write the agent_proposed markdown.

```
You are diagnosing a simulator desync in an Into the Breach solver.

The Rust crate at `rust_solver/src/` is the ONLY simulator. The Python
sim (`src/solver/simulate.py`) was deleted in the simulate.py-removal
PR series — every fix must target Rust source. Responses with
`target_language: python` are auto-rejected.

FAILURE RECORD (failure_db.jsonl entry):
```json
{
  "id": "20260508_134925_472_m02_t02_mech_damage_unexpected",
  "run_id": "20260508_134925_472",
  "mission": 2,
  "turn": 2,
  "severity": "high",
  "details": "PulseMech: predicted HP 2, actual 1 (-1)",
  "solver_version": "rust-0.1.0-9e753ba",
  "simulator_version": 67
}
```

TRIGGERING ACTION (from solve recording):
```json
{}
```

DIFF DETAIL (Layer 1 pretty-printed):
```
(no pretty-printed block; use diff JSON above)
```

DIFF-CATEGORY → SUSPECT-FILE MAP (start here, expand as needed):
```
unit.hp                  apply_damage / apply_damage_core (simulate.rs:230-523),
                         sim_melee CHAIN BFS (simulate.rs:1167-1243),
                         apply_push deadly-terrain + bump (simulate.rs:764-996),
                         sim_projectile (simulate.rs:1247-1333),
                         sim_artillery AoE (simulate.rs:1334-1427)
unit.pos                 apply_push destination (simulate.rs:874),
                         apply_throw / sim_charge / sim_leap (simulate.rs:535-1643),
                         apply_teleport_on_land (simulate.rs:118-144),
                         simulate_action mech move (simulate.rs:1707-1834)
unit.active              simulate_action active-clear at end (simulate.rs:1825),
                         frozen / repair branches (simulate.rs:1788-1817)
unit.{acid,fire,frozen,
       web,shield}        apply_weapon_status (simulate.rs:1002-1087),
                         apply_push status pickup (simulate.rs:886-989),
                         simulate_action move tile pickup (simulate.rs:1765-1775),
                         board.can_catch_fire (board.rs:219-226)
tile.{acid,fire,smoke,
       frozen,cracked}    apply_weapon_status tile branch (simulate.rs:1002-1087),
                         apply_damage_core ice/forest/sand (simulate.rs:341-379),
                         sim_leap smoke transit (simulate.rs:1579-1591)
tile.building_hp /
       tile.terrain        apply_damage_core building/mountain (simulate.rs:298-339),
                         apply_push building bump (simulate.rs:805-847)
grid_power               building destruction grid sync (simulate.rs:327-328),
                         push bump-destroy accounting (simulate.rs:805-843)
spawn / missing_in_*     env_danger v1 vs v2 parsing (serde_bridge.rs:308-343),
                         Artillery emerging-Vek blocking (solver.rs:281-292)
push_dir                 sim_melee PushDir dispatch (simulate.rs:1206-1216):
                         Forward, Flip, Backward, Perpendicular, Outward, Throw
click_miss               solver.get_weapon_targets (solver.rs:156-350)
```

Task:
1. Identify the minimal Rust code change that would bring the sim's
   prediction in line with the observed actual state.
2. Cite exact `file:line`. The harness will Read those line ranges to
   confirm they exist before accepting.
3. Provide a BEFORE / AFTER snippet, ≤20 lines total combined.
4. Confidence levels:
   - high: line exists, fix is consistent with documented game rules,
     and only one semantic change is introduced.
   - medium: fix touches the right region but interaction with adjacent
     code paths needs review.
   - low: best-effort guess; needs human review before apply.

Respond with EXACTLY this JSON shape, and nothing else (no prose, no
markdown fences, no trailing commentary — the harness parses stdout
verbatim):

{
  "target_language": "rust",
  "root_cause": "one-paragraph hypothesis",
  "suspect_files": [
    {"path": "rust_solver/src/simulate.rs", "lines": [START, END]}
  ],
  "fix_snippet": {
    "before": "...",
    "after":  "..."
  },
  "confidence": "high|medium|low",
  "verification_plan": ["step 1", "step 2"],
  "open_questions": []
}
```

## Notes

Generated by `game_loop.py diagnose 20260508_134925_472_m02_t02_mech_damage_unexpected` at 2026-05-08T19:14:57.798571+00:00.
