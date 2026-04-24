# Automated Desync Diagnosis Loop — Design

> Status: **design only**, nothing shipped yet. Start reading at [Rollout order](#rollout-order) if you're implementing.
> Related doc: `docs/self_healing_loop_design.md` (the research gate for unknown pawns/terrain — diagnosis is the sibling loop for sim bugs on *known* pawns).

## 0. Why this exists

The Blitzkrieg/Disposal-Site turn on 2026-04-23 found five independent simulator bugs by hand:

1. Chain Whip hit its own shooter (shooter not seeded in BFS visited set).
2. `PushDir::Perpendicular` silently dropped in `sim_artillery`.
3. ACID pool tile didn't propagate `ACID` status to the unit standing on it at load.
4. Move-only actions incorrectly cleared `unit.active`.
5. (Non-bug — `apply_weapon_status` already paints tile ACID.)

The manual workflow was:
```
verify_action → tail failure_db → eyeball unit_diffs / tile_diffs
    → map each diff to a sim function → propose fix + file:line
    → edit → bump SIMULATOR_VERSION (both files) → archive corpus
    → rebuild wheel → install → regression → commit + push
```

That worked but it's not scalable. This doc specifies the automation.

## 1. Goals & non-goals

**Goals.**
- Every per-action desync gets a human-readable diff summary (not just a category count).
- Most desyncs resolve to a root-cause hypothesis + `file:line` fix proposal without an LLM call, via a seeded rules table.
- Novel signatures trigger an Explore agent whose output conforms to a strict JSON schema.
- Repeat bugs dedupe; aggregate signal surfaces systemic issues.
- The full apply → regression → commit path is one command, opt-in.
- Retired bugs stop re-proposing; rejected fixes stay rejected.

**Non-goals.**
- Automatic fix application is **off by default forever**. Human approves each auto-apply, or nothing ships.
- Fixing Python-side solver (only `rust_solver/src/` is the live sim). Python `src/solver/simulate.py` is test primitives; diagnoses that target it are always wrong.
- Inventing new simulator semantics. Diagnosis only proposes fixes that restore agreement between sim and observed bridge state.

## 2. Four-layer architecture

```
Layer 1 — verify_action prints full diffs inline
   ↓
Layer 2 — game_loop.py diagnose <failure_id>   (markdown proposal, rules + agent fallback)
   ↓
Layer 3 — post-verify hook auto-enqueues diagnosis (rate-limited, dedup, opt-in)
   ↓
Layer 4 — game_loop.py apply_diagnosis <id>    (edit → bump → rebuild → regression → stage commit)
```

Each layer is independently shippable. Plan is 1 → 2 → 3 → 4; ship Layer 1+2 in the first PR.

## 3. Data model

### 3.1 Existing (don't change)

`recordings/failure_db.jsonl` — one line per desync record. Fields we rely on:
```
id, run_id, mission, turn, timestamp, action_index, mech_uid,
category, subcategory, severity, tier, root_cause,
diff: { unit_diffs: [...], tile_diffs: [...], scalar_diffs: [...], total_count },
context: { squad, island, model_gap, weight_version, sim_version, tags },
replay_file, solver_version, simulator_version
```

Diff entries shape:
```
unit_diffs[i] = { uid, type, field, predicted, actual }
tile_diffs[i] = { x, y, field, predicted, actual }     # bridge coords
```

### 3.2 New: `recordings/<run_id>/diagnoses/<failure_id>.md`

One markdown file per diagnosis. Human-readable, grep-friendly, renders in GitHub. Frontmatter YAML for tooling:

```markdown
---
id: 20260423_131700_144_m00_t01_per_action_desync_a2
failure_id: 20260423_131700_144_m00_t01_per_action_desync_a2
run_id: 20260423_131700_144
mission: 0
turn: 1
action_index: 2
sim_version_at_diagnosis: 9
status: pending | rule_match | agent_proposed | applied | rejected | insufficient_data
confidence: high | medium | low
applied_in_commit: null | <sha>
retired_in_sim_version: null | <int>
duplicates_of: null | <failure_id>          # cache key: (diff_signature, sim_version)
target_language: rust | python
proposed_files:
  - path: rust_solver/src/simulate.rs
    lines: [1172, 1175]
rules_matched: [move_only_active_guard]
agent_invoked: false | true
agent_tokens: 0
---

## Symptom
(pretty-printed diff block)

## Hypothesis
(one paragraph)

## Proposed fix
(unified-diff snippet, short)

## Verification plan
(steps; what regression should confirm)

## Notes
(raw agent output, dropped rules, anything)
```

### 3.3 New: `diagnoses/rules.yaml` (in repo, under version control)

Lookup table `(diff_signature) → rule`. Written by humans, added-to over time. Schema:

```yaml
rules:
  - id: move_only_active_guard
    introduced_in_sim_version: 10
    retired_in_sim_version: null
    signature:
      category: null                                # null = don't filter
      unit_diff: { field: active, predicted: false, actual: true }
      action_has_weapon: false
    confidence: high
    hypothesis: >
      simulate_action clears unit.active unconditionally at end of call;
      game leaves mech READY when the plan is move-only.
    suspect_files:
      - rust_solver/src/simulate.rs:1825
    proposed_fix: "guard set_active(false) on weapon_id != WId::None"
    discriminator: "action's weapon_id must be WId::None"
```

Rules have both a **symptom** (what the diff looks like) and a **discriminator** (what else must be true to rule in the hypothesis). Never match on symptom alone — two bugs can produce the same diff.

### 3.4 New: `diagnoses/INDEX.md` (append-only run log)

Not authoritative state; just a human-readable timeline. One line per diagnosis: `<timestamp> | <id> | <status> | <rule_or_agent> | <short desc>`.

### 3.5 New: `diagnoses/known_gaps.yaml`

Explicit list of known unmodelled behaviour (Storm Gen, Psion regen, etc.). Matching diffs get tagged `model_gap=true`, fold into a summary line in Layer 1 output, and are *skipped* by Layer 2 unless `--force`.

### 3.6 New: `diagnoses/rejections.jsonl`

Append-only record of diagnoses the human rejected. Keyed by `(diff_signature, sim_version, proposed_fix_sig)` so the same wrong-proposal can't recur. Layer 2 consults this before emitting a proposal.

### 3.7 Session state (minimal change)

Add to `RunSession` (`src/loop/session.py`):
```python
diagnosis_queue: list[dict] = field(default_factory=list)
# each entry: { failure_id, enqueued_at, status: pending|done|failed }
```

The queue is just a pointer list — the actual markdown lives in `recordings/<run_id>/diagnoses/`. Queue survives session save/load under the existing `fcntl.flock` protection.

## 4. File layout on disk

```
/Users/aircow/Documents/code/claude/ItB/
├── diagnoses/
│   ├── rules.yaml                                       # NEW, in repo
│   ├── known_gaps.yaml                                  # NEW, in repo
│   ├── rejections.jsonl                                 # NEW, in repo (append-only)
│   └── INDEX.md                                         # NEW, in repo (append-only)
├── recordings/
│   ├── failure_db.jsonl                                 # unchanged
│   ├── failure_db_snapshot_sim_v{7,8,9}.jsonl           # unchanged pattern
│   └── <run_id>/
│       ├── m00_turn_01_solve.json                       # unchanged
│       ├── m00_turn_01_action_0_verify.json             # unchanged
│       └── diagnoses/                                   # NEW per-run dir
│           ├── <failure_id>.md
│           └── ...
├── src/
│   └── solver/
│       └── diagnosis.py                                 # NEW module
└── tests/
    └── test_diagnosis_rules.py                          # NEW
```

## 5. CLI surface

```
game_loop.py diagnose <failure_id>                      # Layer 2
    [--force]              # ignore rejection + known_gap guards
    [--agent]              # force agent fallback even if rule matched
    [--no-agent]           # skip agent fallback; exit rule-only
    [--out <path>]         # override markdown output location

game_loop.py diagnose_recent [--turn N] [--mission M]   # Layer 2 batch
    # diagnose every un-diagnosed failure in the last N turns

game_loop.py apply_diagnosis <id>                       # Layer 4
    [--dry-run]            # print the plan; don't edit
    [--skip-regression]    # dangerous; not default
    [--auto-commit]        # commit+push after green regression

game_loop.py reject_diagnosis <id>                      # feed-back rejection
    --reason "one-line explanation"

game_loop.py list_diagnoses                             # index view
    [--status pending|applied|rejected]
    [--since <date>]
```

`verify_action` gains `--diagnose` (Layer 3 trigger) and `--verbose` (Layer 1 always-on verbose).

## 6. Layer 1 — verbose `verify_action` output

Replace the one-line category summary with a field-by-field block:

```
=== DESYNC: Action 2 (ElectricMech Chain Whip at D4) — 6 diffs ===

UNITS:
  WallMech        uid=1    active        pred=false     actual=true      [known-gap: move_only_active_guard]
  ElectricMech    uid=0    hp            pred=1/3       actual=3/3       [novel]
  Scarab2         uid=119  absent        pred=present   actual=absent    [novel: damage-amp on ACID tile]

TILES:
  C3  (5,5)       acid          pred=false     actual=true      [known-gap: acid_tile_fall_to_feet]

CATEGORIES:  push_dir × 1, damage_amount × 2, tile_status × 1, spawn × 2

Known gaps folded: 2 of 6 diffs
Novel diffs:       4 of 6 diffs

Run `game_loop.py diagnose <failure_id>` to produce a fix proposal.
```

Key rules for Layer 1 output:
- Tile coords show **both** bridge `(x,y)` and visual `A1-H8`. Visual is primary (CLAUDE.md rule 10).
- Collapse downstream-cascading diffs: if unit U was mispredicted at action `k` and that triggers N further diffs at actions `>k`, print the first, then `... +N downstream diffs suppressed (run with --show-cascade for detail)`.
- Normalize `predicted death + actual absent`. The diff engine currently emits `missing_in_actual pred=present actual=absent` when the solver predicted HP>0 but actual dropped the unit; if predicted HP<=0 was stored anywhere, collapse to a match.
- Tag each diff with `[novel]` vs `[known-gap: <rule_id>]` vs `[cached: <failure_id>]` (dedup hit).

Implementation: new helper `format_diff_for_log(diff, board, action) -> str` in `src/solver/verify.py` alongside existing `DiffResult`.

## 7. Layer 2 — `diagnose <failure_id>`

### 7.1 Flow

```
load failure_db entry by id
  ↓
if cached (diff_sig + sim_version in diagnoses/ or rejections.jsonl):
    return cached markdown or skip (log "duplicate_of <id>")
  ↓
if tagged known_gap (from known_gaps.yaml or context.model_gap):
    short-circuit: write markdown with status=insufficient_data reason=known_gap
  ↓
rule-match pass:
    for each rule in rules.yaml (active for current sim_version):
        if rule.signature matches diff AND rule.discriminator holds:
            collect candidate
    sort by specificity; require strictly dominant match
    if unique dominant rule:
        write markdown status=rule_match, confidence from rule
        done
  ↓
agent fallback (only if no dominant rule and within agent budget):
    build prompt with:
      - failure_db entry (full)
      - relevant predicted_state slice (only this action, not whole run)
      - relevant actual bridge slice
      - diff-category → code-path map (Section 9)
      - file paths to search
    invoke Explore agent; validate JSON output
    write markdown status=agent_proposed
  ↓
append to diagnoses/INDEX.md
update session.diagnosis_queue[i].status = done | failed
```

### 7.2 Agent prompt template

```
You are diagnosing a simulator desync in an Into the Breach solver.

FAILURE RECORD (failure_db.jsonl entry):
{full JSON}

DIFF DETAIL (pretty-printed):
{Layer 1-style block}

The Rust simulator at /Users/aircow/Documents/code/claude/ItB/rust_solver/src/
is authoritative. src/solver/simulate.py is TEST PRIMITIVES ONLY — never
propose fixes there.

Diff-category → suspect-file map (start here):
{paste Section 9 relevant to this category}

Task:
1. Identify the minimal code change that would bring the sim's prediction
   in line with the observed actual state.
2. Cite exact file:line (verify the line exists before quoting).
3. Provide a BEFORE/AFTER snippet, ≤20 lines total.
4. Confidence: high only if all of (a) the line exists, (b) the fix is
   consistent with game rules as documented in docs/research/, and
   (c) no more than one semantic change is introduced.

Respond in this JSON shape (and nothing else):
{
  "target_language": "rust",
  "root_cause": "...",
  "suspect_files": [{"path": "rust_solver/src/simulate.rs", "lines": [1172, 1175]}],
  "fix_snippet": {
    "before": "...",
    "after":  "..."
  },
  "confidence": "high | medium | low",
  "verification_plan": ["step 1", "step 2"],
  "open_questions": []
}
```

The harness validates:
- `suspect_files[*].path` resolves; `Read` those line ranges and confirm they exist.
- `target_language == "rust"`; reject and retry if python.
- JSON parses; retry once on failure; mark `needs_human` on second failure.

### 7.3 Budget

Agent invocations cost tokens. Defaults:
- Max 2 agent calls per turn.
- Skip entries tagged `model_gap_known: true` unless `--force`.
- Dedupe by `(diff_signature, sim_version)` — cache hit returns stored markdown.
- `diagnose_recent` processes at most N unique signatures, not N raw entries.

## 8. Layer 3 — post-verify auto-hook

New flag on `verify_action`: `--diagnose` (also enabled by env var `ITB_AUTO_DIAGNOSE=1`).

When set, after `append_to_failure_db()` in `src/loop/commands.py:1762-1777`:

```python
if auto_diagnose_enabled():
    session.diagnosis_queue.append({
        "failure_id": desync_record["id"],
        "enqueued_at": now_iso(),
        "status": "pending",
    })
    session.save()
    # actual diagnosis runs out-of-band; never blocks this command
```

The **main Claude harness** (outside Python — Claude Code's agent loop) is the one that picks up the queue:
- After each `verify_action` call, Claude reads `session.diagnosis_queue`.
- For each pending entry, Claude runs `game_loop.py diagnose <failure_id>`.
- Layer 2 handles rules vs agent internally.
- Claude surfaces `status=agent_proposed|rule_match` diagnoses at end-of-turn for human review.

This is the same pattern as the existing research-queue flow (`cmd_research_next`, `session.research_queue`).

**Critical:** diagnose NEVER runs on the hot path inside `auto_turn`. Enemy animation timing is 45s-sensitive (CLAUDE.md rule 7); a diagnosis call would blow that budget.

## 9. Diff-category → sim-code map (seed, Section 3 of Agent 2 output)

See [Section 9 appendix](#appendix-a-diff-category-map) at the end of this doc — it's long enough to keep separate.

## 10. Seed rules table (to land in `diagnoses/rules.yaml`)

From Agent 1's corpus sweep + our five fixes:

```yaml
rules:
  # From our 2026-04-23 fixes
  - id: move_only_active_guard
    introduced_in_sim_version: 10
    signature:
      unit_diff: { field: active, predicted: false, actual: true }
      action_has_weapon: false
    confidence: high
    suspect_files: [rust_solver/src/simulate.rs:1825]

  - id: chain_shooter_self_damage
    introduced_in_sim_version: 10
    signature:
      unit_diff: { field: hp, actual_greater_than_predicted: true }
      unit_is_attacker: true
      weapon_flag: CHAIN
    confidence: high
    suspect_files: [rust_solver/src/simulate.rs:1172]

  - id: artillery_perpendicular_push_missing
    introduced_in_sim_version: 10
    signature:
      unit_diff: { field: pos, unit_adjacent_to_target: true }
      weapon_type: Artillery
      weapon_push: Perpendicular
    confidence: high
    suspect_files: [rust_solver/src/simulate.rs:1360]

  - id: acid_tile_unit_status_at_load
    introduced_in_sim_version: 10
    signature:
      unit_diff: { field: hp, actual_less_than_predicted: true }
      target_tile_has: acid
      unit_had: { acid: false }
    confidence: high
    suspect_files: [rust_solver/src/serde_bridge.rs:440]

  # From Agent 1 corpus sweep (confidence: medium, need in-game verification)
  - id: spawn_bfs_propagation
    introduced_in_sim_version: null      # not fixed yet
    signature:
      unit_diff: { missing_in_actual: true }
      category: spawn
    confidence: medium
    suspect_files:
      - rust_solver/src/simulate.rs:1170
      - rust_solver/src/simulate.rs:apply_spawn  # locate exact line in implementation
    hypothesis: >
      612-count signature; units predicted present but actually absent,
      concentrated in swarm Vek types (Firefly1, Bouncer1, Leaper1).
      Likely chain-visited or spawn-blocking bug.

  - id: damage_amount_underestimate
    introduced_in_sim_version: null
    signature:
      unit_diff: { field: hp, pred_minus_actual: { range: [1, 3] } }
    confidence: medium
    suspect_files: [rust_solver/src/simulate.rs:244]
    hypothesis: >
      333 diffs; pred 1→2 (84x), pred 2→3 (60x). Suspect armor/acid/shield
      modifier not applied or double-applied.

  - id: forest_terrain_not_destroyed
    introduced_in_sim_version: null
    signature:
      tile_diff: { field: terrain, predicted: Forest, actual: Ground }
    confidence: high
    suspect_files: [rust_solver/src/simulate.rs:366]
    hypothesis: >
      156 diffs; forest tiles not converting to ground after weapon damage.

  - id: smoke_not_applied
    introduced_in_sim_version: null
    signature:
      tile_diff: { field: smoke, predicted: false, actual: true }
    confidence: medium
    suspect_files: [rust_solver/src/simulate.rs:1009]
    hypothesis: >
      171 diffs; smoke applied in actual but not predicted. Check
      apply_weapon_status smoke branch + per-weapon SMOKE flag routing.

  - id: death_overprediction
    introduced_in_sim_version: null
    signature:
      unit_diff: { field: alive, predicted: false, actual: true }
    confidence: medium
    suspect_files: [rust_solver/src/simulate.rs:230]
    hypothesis: >
      168 diffs; solver predicts kill, unit survives. Inverse of
      damage_amount_underestimate + shield/armor not applied in sim.
```

Each rule must evolve as bugs get fixed: set `retired_in_sim_version` when the underlying bug lands. Diagnose skips retired rules.

## 11. Layer 4 — `apply_diagnosis <id>`

Strict sequence:

```
1. Load diagnoses/<id>.md; verify status in (rule_match, agent_proposed).
2. Verify no uncommitted diff in proposed files:
     git status --porcelain <target_files> must be empty.
     Else refuse; emit diagnoses/<id>/proposed.patch for manual review.
3. Apply the fix_snippet (before → after replacement via Edit tool).
4. Detect semantic change:
     If sim files changed (rust_solver/src/*.rs, src/solver/verify.py,
     src/solver/simulate.py), require SIMULATOR_VERSION bump.
5. If bump required:
     a. cp recordings/failure_db.jsonl
          recordings/failure_db_snapshot_sim_v<old>.jsonl
     b. Bump rust_solver/src/lib.rs SIMULATOR_VERSION constant (+1).
     c. Bump src/solver/verify.py SIMULATOR_VERSION constant (+1).
     (Atomic bump — pre-commit hook refuses one without the other;
      memory note: feedback_simulator_version_atomic_bump.md)
6. cd rust_solver && maturin build --release; capture stderr.
     If fail: revert edits; mark diagnosis build_failed; exit.
7. pip install --user --force-reinstall the new wheel.
8. bash scripts/regression.sh
     If fail: revert edits (incl. version bumps + archive cp); mark
     diagnosis regression_failed; exit non-zero.
9. If --auto-commit:
     git add <touched files> recordings/failure_db_snapshot_sim_v*.jsonl
     git commit with diagnosis id in trailer
     git push origin main   (per feedback_auto_push.md)
   Else: stage + leave for human review.
10. Update diagnoses/<id>.md frontmatter:
      status=applied
      applied_in_commit=<sha>
      applied_at=<iso>
    Append to diagnoses/INDEX.md.
```

Invariants:
- Regression is mandatory. No flag disables it except `--skip-regression` which refuses to `--auto-commit`.
- Version bump is atomic and archives the corpus first, matching existing memory rule.
- Pre-commit hook already runs regression on sim-code changes (confirmed in recent commits).

## 12. Rejection feedback

```
game_loop.py reject_diagnosis <id> --reason "wrong direction; actual cause is X"
```

Appends to `diagnoses/rejections.jsonl`:
```json
{"failure_id": "<id>", "diff_signature": "<sig>", "sim_version": 10,
 "proposed_fix_sig": "<sha-of-fix-snippet>", "reason": "...",
 "rejected_at": "..."}
```

Layer 2 consults this file before running agent fallback. If the same `(diff_signature, sim_version, proposed_fix_sig)` is in rejections, skip it — never re-propose.

## 13. Edge cases (full list from Agent 4)

### Layer 1 — verbose verify_action
1. **Cascading downstream diffs.** One mispredicted push at action `k` shifts every later unit position, producing N diffs for 1 bug. *Mitigation:* tag diffs with `provenance_action_idx`; collapse diffs whose source tile matches an earlier diff's affected tile; add `--show-cascade` flag for detail.
2. **Two bugs in one turn.** Blended diff confuses any single rule. *Mitigation:* cluster diffs by spatial locality + action index; emit `cluster_id`; Layer 2 diagnoses each cluster independently.
3. **Coord confusion.** Bridge `(x,y)` vs visual `A1-H8`. *Mitigation:* always print both, visual primary.
4. **Corpse diffs.** Solver predicts death; actual drops the unit. *Mitigation:* normalize predicted-HP≤0 to "absent" before comparison.
5. **Chronic known-gap drown-out.** Storm Gen / Psion regen diffs recur every turn. *Mitigation:* `known_gaps.yaml` filter; folded into summary line.
6. **Serialization nondeterminism.** HashMap iteration, spawn slot RNG. *Mitigation:* canonicalize serialization; compare by key.
7. **Cosmetic status diffs** with no HP consequence. *Mitigation:* severity weighting — effect-only diffs become `info`, not `error`.

### Layer 2 — diagnose
8. **Two rules match same diff.** *Mitigation:* require strictly dominant match; else agent fallback.
9. **Rule fires on a symptom-only match but actual cause is different.** *Mitigation:* rules must have `symptom` AND `discriminator`; never match on symptom alone.
10. **Rule-table drift.** A rule for sim_v7 keeps firing after sim_v8 fix. *Mitigation:* each rule has `introduced_in_sim_version` and `retired_in_sim_version`; retired rules skipped.
11. **Agent hallucinates file:line.** *Mitigation:* validator Reads the cited range; if missing, retry once, else mark `needs_human`.
12. **Agent proposes Python fix when Rust is authoritative.** *Mitigation:* prompt pins "Rust authoritative"; validator rejects `target_language=python`.
13. **Agent returns malformed JSON.** *Mitigation:* one retry on parse failure; save raw on second failure; mark `needs_human`.
14. **Insufficient data.** Diagnosis needs animation order or screenshot. *Mitigation:* agent may return `status=insufficient_data` with a `request` list; Layer 3 can fulfil next turn.
15. **Recurring diagnosis of same bug.** *Mitigation:* `(diff_signature, sim_version)` hash; cache hit returns stored markdown.
16. **Confidence calibration.** Agent always says "high". *Mitigation:* require ≥2 code locations + expected sim-prediction delta; downgrade to medium if either missing.

### Layer 3 — auto-trigger
17. **Diagnose on hot path.** Blocks `auto_turn`'s 45s enemy-animation window. *Mitigation:* Layer 3 always async / post-turn; NEVER on hot path.
18. **Unwanted categories recur.** *Mitigation:* `config/diagnose_ignore.yaml` with `{categories, pawn_types, weapon_ids}`.
19. **Concurrent diagnose on same id.** *Mitigation:* `fcntl.flock` on `diagnoses/<id>.lock`.
20. **Missing recording file.** Snapshot pruned. *Mitigation:* degrade to diff-only mode; mark `recording_missing=true`; never crash.
21. **Bridge dead.** *Mitigation:* diagnose only reads on-disk artifacts.
22. **Mission end mid-diagnosis.** *Mitigation:* write to `diagnoses/pending/`; flush on commit.

### Layer 4 — auto-apply
23. **Fix regresses corpus.** *Mitigation:* `scripts/regression.sh` mandatory; abort + revert on fail.
24. **Forgot SIMULATOR_VERSION bump.** *Mitigation:* pre-commit hook refuses semantic sim change without atomic bump in both files.
25. **Bump without corpus archive.** *Mitigation:* archive is step 5a before bump; failed cp fails closed.
26. **Rebuild fails.** *Mitigation:* capture stderr; revert; never commit half-built state.
27. **Stale regression corpus.** *Mitigation:* `scripts/regression.sh` filters by `sim_version >= current − 1`; older entries informational.
28. **Commit conflicts with user work.** *Mitigation:* refuse commit if `git status --porcelain <target_files>` non-empty; emit patch for manual review.
29. **Revert an auto-applied fix.** *Mitigation:* commits tagged `auto-fix/<diagnosis_id>`; `game_loop.py revert_diagnosis <id>` does clean `git revert`.
30. **Rejected fix gets re-proposed.** *Mitigation:* rejections feed back into rules table; dedupe key honors rejection.

### Cross-cutting
31. **Reset-Turn button used mid-mission.** Invalidates all predicted_state for that turn. *Mitigation:* bridge exposes `turn_reset_count`; verify_action aborts diff and tags recording `stale_due_to_reset`.
32. **Pilot swap / shop weapon mid-run.** Old rules keyed on weapon_id no longer apply. *Mitigation:* rules match on `(weapon_id, sim_version)`; diffs carry `loadout_hash`.
33. **Disk bloat.** *Mitigation:* `tools/gc_diagnoses.py` — keep last 200 + all `applied`/`rejected`.
34. **Agent context window overflow.** *Mitigation:* feed only the action's `predicted_states[i]` + `actual_board.json` + failure_db entry. NEVER whole run.
35. **Parallel runs overwriting `active_session.json`.** *Mitigation:* session file carries `pid`; second process warns + exits (existing fcntl lock already handles this).

## 14. Testing strategy

`tests/test_diagnosis_rules.py` — `@pytest.mark.regression`:
- Fixture: known-bug board JSONs under `tests/known_bug_boards/`.
- Each fixture asserts: `diagnose(fixture.failure_id)` returns the expected rule id + file:line.
- Fixtures are the durable contract — they protect against rule regressions.

Seed fixtures (one per rule in seed table):
1. `move_only_wallmech_active_mismatch.json` — from commit f00a394 source.
2. `chain_whip_selfdamage_d5.json` — same turn.
3. `artillery_perpendicular_push_c3.json` — same turn.
4. `acid_tile_scarab2_d4.json` — same turn.

## 15. Rollout order

**PR 1 — Layer 1** (half day): verbose diff printer + visual-coord helper.
- Add `format_diff_for_log(diff, board, action)` in `src/solver/verify.py`.
- Hook into `cmd_verify_action` in `src/loop/commands.py:1762-1777`.
- No new commands, no new files, no flag.

**PR 2 — Layer 2 foundation** (one day): rules-only diagnose.
- New module `src/solver/diagnosis.py` with `load_rules()`, `match_rule(diff, sim_version) -> Rule | None`, `write_markdown(failure_id, rule) -> path`.
- New command `cmd_diagnose` in `src/loop/commands.py`; wire in `game_loop.py`.
- Seed `diagnoses/rules.yaml` with the 4 rules from our recent fixes.
- Seed `diagnoses/known_gaps.yaml` with model_gap entries from failure_db.
- Tests: `test_diagnosis_rules.py` with 4 fixtures.
- **No agent invocation yet.** Rules-only coverage.

**PR 3 — Layer 2 agent fallback** (one day): add Explore-agent dispatch for no-rule-match cases.
- Agent budget env var: `ITB_DIAGNOSE_AGENT_BUDGET` (default 2 per `diagnose_recent` call).
- Validator for agent output.
- `reject_diagnosis` command.
- Append medium-confidence rules from Agent 1 corpus sweep (`spawn_bfs_propagation`, etc.) after validating 1-2 in-game.

**PR 4 — Layer 3 auto-trigger** (half day): flag + queue hook in verify_action.
- `verify_action --diagnose` + env var.
- Session `diagnosis_queue` field.
- Dedup by `(diff_signature, sim_version)`.
- Main-harness (Claude's own loop) drains the queue between turns.

**PR 5 — Layer 4 apply + commit** (one day): the automation.
- `cmd_apply_diagnosis` with strict sequence from Section 11.
- Pre-commit hook (or extend existing) for atomic SIMULATOR_VERSION bump check.
- `game_loop.py revert_diagnosis <id>` with `git revert` on tagged commit.
- Explicit `--auto-commit` flag; never default.

## 15.1 Post-shipping retrospective + known limitations

PR1–PR5 shipped 2026-04-23 / 2026-04-24. PR6 was a live integration run on
`20260423_131700_144_m00_t01_per_action_desync_a0` — no production code
changed; instead it surfaced four rough edges that are now patched or
documented.

### Patched in PR6

1. **`dirty_targets` lopped the first letter of the path.** The slicer
   did `proc.stdout.strip().splitlines()`, but `git status --porcelain`
   formats worktree-only changes as `" M PATH"` with a leading space
   (the X status). `proc.stdout.strip()` ate that leading space and
   shifted every byte of the first line one position to the left, so
   `line[3:]` returned `"ust_solver/src/lib.rs"`. Fix: don't strip the
   whole stdout — split first, slice each line at column 3 individually.
   Regression: `test_dirty_targets_preserves_leading_space_in_path`.

2. **Validator rejected prose-wrapped JSON.** Agents reason aloud, then
   commit to a final JSON block. `_parse_agent_json` previously accepted
   only bare JSON or a single ` ``` ` fence wrapper, so realistic agent
   output failed. Fix: brace-balance the response and accept the LAST
   complete top-level `{...}` block. Skips braces inside string literals
   so Rust code in `fix_snippet.before` doesn't fool the balancer.
   Regressions: `test_validate_extracts_last_json_from_prose_wrapped_response`,
   `test_validate_skips_braces_inside_strings`.

### Known limitation — multi-location fixes

`fix_snippet` is a single `{before, after}` pair. Real Rust fixes often
touch multiple sites at once — adding a parameter to a function requires
editing both the signature AND every call site. The agent on PR6
proposed exactly this kind of fix and the apply path can't express it.

Workaround for now: agent should propose fixes that are *local* — a
guard added inside an existing function, a missed branch in a match arm,
a flag flipped in `WeaponDef`. When a multi-location refactor is the
right answer, the agent should return `confidence: low` with an
`open_questions` entry asking a human to do it.

Real fix (deferred): change `fix_snippet` to a list of per-file
`{path, before, after}` entries. Schema change touches the validator,
the markdown writer, `apply_fix`, and the rules.yaml shape if rules
ever grow Edit-able fixes. One PR's worth of work; not ahead of
demonstrated need.

## 16. Metrics to track (future)

These aren't needed for v1 but worth planning the data shape now:

- Time-to-diagnosis per failure (p50, p95).
- Rule-match rate (% desyncs resolved without agent).
- Agent-fix first-time success rate (% that pass regression without edit).
- Rejection rate by rule id (signals a bad rule).
- Mean time-to-fix per systemic category.

Log these to `diagnoses/metrics.jsonl` in Layer 3.

---

## Appendix A. Diff-category → sim-code map

This map answers "which function produced this wrong output" for each diff category. Agent 2 audited the Rust sim to build it. Cite exact `file:line` — don't guess.

### Unit-level diffs

#### `unit.hp` differs
Priority suspects:
1. `rust_solver/src/simulate.rs:484-523` — `apply_damage()` standard entrypoint; pre-checks Blast Psion death + Volatile decay, dispatches to apply_damage_core.
2. `rust_solver/src/simulate.rs:230-433` — `apply_damage_core()`; HP subtraction with armor/acid/shield/frozen modifiers (237-268); drown on ice→water (341-362); mine kills (412-422); web breaks (425-432).
3. `rust_solver/src/simulate.rs:1167-1243` — `sim_melee()`; damage + chain BFS (1175-1200).
4. `rust_solver/src/simulate.rs:764-996` — `apply_push()`; bump damage on blocker (867-868); deadly-terrain kills (925-951); Old Earth Mine instakill (957-978).
5. `rust_solver/src/simulate.rs:1247-1333` — `sim_projectile()`; mountain damage passthrough (1255-1283).
6. `rust_solver/src/simulate.rs:1334-1427` — `sim_artillery()`; AoE damage (1340-1400).
7. `rust_solver/src/simulate.rs:56-92` — `apply_death_explosion()`; Blast Psion chain (1 bump).
8. `rust_solver/src/simulate.rs:27-54` — `apply_volatile_decay()`; Volatile Vek adjacent damage.

Filter by context:
- Weapon has `CHAIN` flag → chain BFS (1175-1200) first.
- Unit pushed this turn → apply_push deadly-terrain / mine (925-978).
- Volatile Vek alive → check death-explosion depth.
- Ice→water transition → apply_damage_core 341-362.
- Mine trigger → simulate_action mine paths (1742-1762).
- Known TODO: `simulate.rs:439` — flood_tile bypasses Blast Psion credit.

#### `unit.pos` differs
1. `rust_solver/src/simulate.rs:764-996` — `apply_push()`; destination (874: `units[idx].x/y = nx/ny`).
2. `rust_solver/src/simulate.rs:535-728` — `apply_throw()`; Vice Fist toss (559-560).
3. `rust_solver/src/simulate.rs:1486-1539` — `sim_charge()`; last-free tile (1516).
4. `rust_solver/src/simulate.rs:1543-1643` — `sim_leap()`; land on target (1569).
5. `rust_solver/src/simulate.rs:118-144` — `apply_teleport_on_land()`; swap (134-142).
6. `rust_solver/src/simulate.rs:1707-1834` — `simulate_action()`; mech move (1719-1720).

Filter:
- Push direction mismatch → apply_push direction calc (776).
- Charge overshoot → last-free logic (1496-1512).
- Teleport missed → move_to vs old_pos guard (1783).
- Unit survived lethal terrain → deadly-ground check (917-930).

#### `unit.active` differs
1. `rust_solver/src/simulate.rs:1707-1834` — `simulate_action()`; active clear at 1831 only on weapon fire (POST sim_v10 fix).
2. Lines 1814-1817 — frozen mech clears active unconditionally.
3. Lines 1788-1810 — repair clears active.

#### `unit.{acid,fire,frozen,web,shield}` differs
1. `rust_solver/src/simulate.rs:1002-1087` — `apply_weapon_status()`; fire 1050-1063, acid 1065-1067, freeze 1068-1074, web 1075-1082, shield 1083-1085; shield guard 1042.
2. `rust_solver/src/simulate.rs:764-996` — `apply_push()`; fire pickup 886-891, acid pickup 893-899, freeze mine 981-989, OEM override 983-987.
3. `rust_solver/src/simulate.rs:1707-1834` — `simulate_action()`; mech move fire/acid/mine 1765-1775; repair status clear 1792-1795.
4. `rust_solver/src/board.rs:219-226` — `can_catch_fire()`; Pilot_Rock + Flame Shielding.

Filter:
- Web immunity → apply_weapon_status 1079 (Soldier/Camila).
- Shield absorbs status → guard 1042.
- Fire extinguish on freeze → 1070-1071.
- Freeze unfreeze on fire → 1052-1053.

#### `unit.missing_in_actual` (solver over-predicted survival)
1. `rust_solver/src/simulate.rs:230-433` — apply_damage_core kill paths.
2. `rust_solver/src/simulate.rs:764-996` — apply_push drowns/mines/bump.
3. `rust_solver/src/simulate.rs:465-479` — `trigger_dam_flood()`.
- Known gap: flood_tile doesn't trigger Blast Psion (line 439 TODO).

#### `unit.missing_in_predicted` (solver missed a kill)
- env_danger vs env_danger_v2 parsing (serde_bridge.rs:338-341).
- Shield/frozen/armor/ACID modifiers mis-applied (237-268).
- Drown immunity mischecked (350-357).

### Tile-level diffs

#### `tile.{acid,fire,smoke,frozen,cracked}` differs
1. `rust_solver/src/simulate.rs:1002-1087` — apply_weapon_status (acid 1026-1035).
2. `rust_solver/src/simulate.rs:230-433` — apply_damage_core; ice transitions (341-362), forest ignite (364-370), sand→smoke (372-379).
3. `rust_solver/src/simulate.rs:1543-1643` — sim_leap; smoke-leap transit (1579-1591).
4. `rust_solver/src/simulate.rs:1707-1834` — simulate_action; mech move fire (1769-1774).
5. `rust_solver/src/board.rs:37-52` — tile flag setters.

#### `tile.building_hp` / `tile.terrain` differs
1. `rust_solver/src/simulate.rs:230-433` — apply_damage_core; building destruction (298-325), mountain 2HP→rubble (330-339).
2. `rust_solver/src/simulate.rs:764-996` — apply_push; building bump (816-847), mountain collision (789-800), grid-power (805-843).
3. Grid sync: 327-328, 835-842.

#### `tile.has_pod` differs
1. `rust_solver/src/simulate.rs:1707-1834` — simulate_action; pod collection on mech move (1723-1729).
2. `rust_solver/src/serde_bridge.rs:290-302` — bridge load.

### Scalar diffs

#### `grid_power` differs
1. `rust_solver/src/simulate.rs:230-433` — building grid cost on destruction (327-328).
2. `rust_solver/src/simulate.rs:764-996` — bump-destroy accounting (805-843). Regression comment 812-815: multi-HP buildings.

#### `active_mechs` count differs
1. `rust_solver/src/board.rs:452-464` — `active_mechs()` filter.

### Other diffs

#### `spawn` category
1. `rust_solver/src/serde_bridge.rs:308-343` — env_danger v1 vs v2 parsing.
2. `rust_solver/src/solver.rs:281-292` — Artillery enum emerging-Vek blocking.

#### `push_dir` category
1. `rust_solver/src/simulate.rs:1167-1243` — sim_melee PushDir dispatch (1206-1216): Forward, Flip, Backward, Perpendicular, Outward, Throw.
2. Direction math: DIRS[] (776), `opposite_dir()` (1209), `(dir+1)%4` (1230).

#### `click_miss` category (solver enumerated invalid target)
1. `rust_solver/src/solver.rs:156-350` — `get_weapon_targets()`:
   - Melee 168-211; throw validation 185-200.
   - Projectile/Laser 213-242; building-block 221-239.
   - Pull 244-279; range_min/max with blocker (sim_v9 fix).
   - Artillery 281-292; axis-aligned.
   - Charge 297-304; cardinal neighbors.
   - Leap rest; open-tile landing.

#### `damage_amount` category
1. `rust_solver/src/simulate.rs:230-433` — apply_damage_core modifiers (244-268): armor -1, acid ×2, Force Amp +1 bump.
2. Shield absorb (237-239).
3. Frozen immunity (240-242).

## Appendix B. Current sim known-gaps (seed `known_gaps.yaml`)

From code comments and failure_db `model_gap=true` tags:

```yaml
known_gaps:
  - category: status
    field: unit.web
    pred: true
    actual: false
    count: 153
    reason: "Non-deterministic web-clearing on mech push; not yet modelled."
  - category: tile_status
    field: tile.smoke
    reason: "Some Vek attack smoke behaviors not routed through apply_weapon_status."
  - code_comment: "simulate.rs:439 TODO(dam-integration)"
    reason: "flood_tile drown deaths don't trigger Blast Psion explosion chain."
  - pawn_type: Jelly_Armor1
    reason: "Shell Psion 'ALL OTHER Vek' exclusion rule partially implemented."
```

Matching entries in failure_db get tagged `model_gap=true` automatically at Layer 1 formatting time; Layer 2 skips them unless `--force`.
