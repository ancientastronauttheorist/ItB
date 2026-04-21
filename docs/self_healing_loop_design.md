# Self-Healing Loop Design

**Status:** in progress (revised 2026-04-20).

Phase 0 instrumentation is shipped (`src/solver/unknown_detector.py`, `src/solver/fuzzy_detector.py`, `data/known_types.json`). Phase 2 research modules exist in `src/research/` (capture, vision, wiki_client, comparator, orchestrator). Phase 3 overrides and Phase 4 P4-1/P4-2 auto-drafter landed per recent commits.

The loop does not yet close on its own — detection signals are advisory; research doesn't auto-fire. See **Missing wire** at the end.

Timing: revised from "between turns" to **inline per turn**. See Research section.

**Goal:** turn solver desyncs from post-hoc training data into a closed feedback loop that detects, responds to, and researches unknown or drifted game behavior during a run, then feeds validated findings back into the solver between runs.

## Why now

Two bugs shipped recently (Solar Farm bridge gap, mountain damage sim gap) were both discovered after long reactive debugging. Each required human reasoning to chain from "desync on turn 2" to "bridge doesn't iterate Criticals" or "apply_damage has no Mountain branch." A disciplined detector that says "weapon X keeps producing building_hp diffs on mountains" would have pointed at the root cause in one step. Scaling the bot to all 70 achievements means hitting more unexplored combinations — we need this to be structural.

## Research findings that constrain the design

- **pyo3 `.so` modules cannot be reloaded in a running Python process.** Rebuild + process restart is the only way to pick up new Rust code. This kills any "rebuild mid-run" path.
- **Rust weapon definitions are a compile-time `static` array** at `rust_solver/src/weapons.rs:246`. No runtime override exists today, but adding a JSON-override field to the solve call is ~3 files and one rebuild (see Phase 3).
- **Python `src/solver/simulate.py` is not in the hot path** — it's parity-only. Hot-patching it doesn't affect live play.
- **`RunSession` has no per-run event state.** Trivial to add.
- **No OCR in the codebase.** Claude Vision on small crops is the lightest path for tooltip extraction.
- **Classification pipeline is mature.** `src/solver/verify.py:classify_diff` already emits 12 categories and a `model_gap` flag. We extend, not replace.
- **Fandom wiki has a MediaWiki API** that's structured enough for an automated client. Steam forum threads are too freeform for auto-scrape.
- **Rust rebuild is ~9.3s** (measured). Fine between missions, catastrophic mid-turn.

## System architecture

Three subsystems, each independently deployable:

```
                    ┌────────── DETECTION ──────────┐
  bridge read ────▶ │ unknown_detector → unknowns  │ ──▶ session.failure_events_this_run
                    │ fuzzy_detector → signals     │
                    │ (hook after classify_diff)   │
                    └──────┬───────────────┬───────┘
                           │ signals       │ unknowns + 'unknown_behavior' tags
                           ▼               ▼
                    ┌── RESPONSE ──┐  ┌──── RESEARCH (inline) ────────┐
                    │ Tier 1..4    │  │ hover + Vision tooltip (MCP)  │
                    │ (existing)   │  │ wiki_raw scrape → MediaWiki   │
                    │              │  │ Steam forum / Reddit (WebFetch)│
                    │              │  │ comparator → override staging │
                    │              │  │ writes data/wiki_raw/<T>.json │
                    └──────────────┘  └───────────────────────────────┘
```

## Detection

### Hook point

`src/loop/commands.py:2471`, immediately after `classify_diff` returns inside `cmd_auto_turn`. At this point `diff`, `classification`, `mech_uid`, `action_index`, `phase` (post_move / post_attack), `turn`, and `sub_action` are all in scope. All subsequent signals derive from these.

### Signals

| Signal | What it tells us | Source |
|---|---|---|
| **Category** | Which sim subsystem drifted | existing `classify_diff` |
| **Model-gap flag** | Known-unfixed sim bug | existing `model_gap` bool |
| **Sub-action provenance** | post_move vs post_attack = movement vs weapon bug | `sub_action` field |
| **Diff topology** | Outside AOE footprint = geometry wrong; inside = magnitude | compare tile_diffs coords to weapon AOE mask |
| **Asymmetry** | Over- vs under-estimate killing | unit missing flip direction |
| **Frequency × specificity** | Systemic vs noise | in-memory window `failure_events_this_run` |
| **Type novelty** | Unit/terrain never seen in this codebase | `known_types.json` lookup |
| **Bridge gap** | Field present in save file, absent from bridge | save-parser cross-check |

Each signal emits a confidence score (0–1) and a proposed response tier.

### New artifacts

- `src/solver/fuzzy_detector.py` — pure function `evaluate(diff, classification, context) → FuzzySignal`.
- `src/solver/unknown_detector.py` — pure function on bridge state: `detect_unknowns(board) → {types: [...], terrain_ids: [...]}`.
- `data/known_types.json` — generated from `data/wiki_raw/` filenames + Rust weapon/enemy enums. Regenerated when those change.
- `RunSession.failure_events_this_run: list[dict]` and `RunSession.research_queue: list[dict]` — persisted with existing session serializer.

## Response

Four tiers in escalating order. Pick by signal severity.

### Tier 1 — re-solve from bridge state

Already in place in `cmd_auto_turn`. No change.

- **Pros:** free; bounded; always correct (bridge is ground truth).
- **Cons:** doesn't prevent recurrence of the same bug on the next action.

### Tier 2 — soft-disable suspect actions

Maintain a runtime blocklist per session:

```python
session.disabled_actions: list[{
  "weapon_id": int,
  "cause_pattern": str,     # e.g. "aoe_contains_mountain"
  "expires_turn": int,
  "strategic_override": bool  # if True, strategist can still pick it
}]
```

Solver integration: the evaluator adds a large negative score bias to any action matching an entry. Not a hard prohibition — if no alternative scores well, the solver can still pick it.

- **Pros:** zero rebuild; fully reversible; narrow blast radius.
- **Cons:** doesn't fix the bug, just avoids it. Possible to over-blocklist and render a mech useless (mitigation: expiry + strategic_override flag).

Expiry rule: remove entry after `N=3` turns OR when board topology changes meaningfully (new enemy spawn, building destroyed). Reset at mission boundaries.

### Tier 3 — JSON weapon override

Defer to Phase 3 if Tier 2 proves insufficient. Requires one-time Rust surgery (scoped by audit: 3 files, ~50 lines). Once shipped, patches land as JSON entries in `weights/weapon_overrides.json`:

```json
{
  "33": {
    "damage_to_mountain": true,
    "sand_to_smoke_ignites_on_fire_flag": true
  }
}
```

Loaded at `solve()` time, passed into Rust via the JSON input, merged into the weapon-def lookup.

- **Pros:** fixes the bug, not just avoids it.
- **Cons:** Rust rebuild + process restart required to ship the override mechanism itself (9.3s one-time). Each override entry needs a regression board fixture. Risk of override making things worse.

Gate: an override entry cannot be applied unless a regression board under `tests/weapon_overrides/<weapon>_<case>.json` demonstrates both the bug and the fix.

### Tier 4 — narrate and continue

When signal confidence is low or no safe response exists, emit `{"event": "solver_gap_detected", "signal": ..., "context": ...}` in the `auto_turn` result. Claude summarizes it for the user; the loop proceeds. The event also enqueues a research task.

- **Pros:** visibility with zero risk.
- **Cons:** no mitigation — the next identical action will desync again.

## Research

Runs **inline the moment an unknown is detected during `cmd_read`**, before the solver runs. Revised 2026-04-20 from the original deferred-between-turns model.

Rationale: an unresolved unknown is a desync waiting to happen. ITB is turn-based with no timer, so pausing to research before the move is safer than playing blind and repairing the record after the fact. First-turn stalls in missions with multiple novel enemies are acceptable; subsequent turns in the same run hit the registry and fire-through with zero latency.

The original "visual stall + recursion risk" concerns are handled by: (a) `snapshot <auto-label>` before the orchestrator runs, (b) strict dedup on the `(type, terrain_id, weapon_id, screen_id)` tuple so the orchestrator never re-enters on the same target, (c) a hard per-unknown timeout — on failure, the target drops to the deferred queue below and the loop narrates + continues.

### Queue

`RunSession.research_queue` — list of `{type, terrain_id, weapon_id, screen_id, mission_id, first_seen_turn, attempts}`. Deduped by that tuple. Persists across sessions.

In the inline model the queue holds **unknowns that failed to resolve inline** (Vision low-confidence, wiki miss, network fail, timeout). Those drop to the original deferred-between-turns path — processed before the next mission starts. Successful inline resolutions never hit the queue.

### In-game tooltip capture

Three crops from the post-click UI, with pixel regions to be calibrated per-build in the first implementation ticket:

- **Name tag** (bottom-left): unit name, HP pips. Smallest crop.
- **UNIT STATUS panel** (center-bottom): portrait, name, move stat.
- **Weapon preview panel** (right of UNIT STATUS): weapon name, one-line description, **rendered mini-board showing exact AOE geometry**, damage number.

The weapon preview panel is the most valuable of the three. The mini-board shows tile-accurate ground truth for the AOE footprint, push directions, and targeting pattern — the exact information the Rust `WeaponDef` encodes. This turns Phase 2 from "read names" into a **regression harness for weapon definitions**.

MCP sequence:
1. `mouse_move` to a neutral tile (dismiss any residual tooltip).
2. `left_click` the target unit.
3. `screenshot` (panels appear on selection — no hover needed for the enemy case).
4. `zoom` each of the three crop rectangles.
5. Send each crop to Claude Vision with a structured prompt:
   - Name + HP crop: `"Read the unit name and HP count."`
   - Weapon preview crop: `"This is an Into the Breach weapon preview. Return JSON: {name, description, damage, footprint_tiles, push_directions}."`
6. Diff the extracted geometry against `rust_solver/src/weapons.rs` for that weapon. Flag mismatches.

For **terrain** tooltips, hover is needed (different code path). Pixel region also TBD — see **Missing wire** below.

### External research (Fandom MediaWiki API)

```
GET https://intothebreach.fandom.com/api.php
  ?action=query&titles=<Name>&prop=wikitext&format=json
```

Cache to `data/wiki_raw/<Name>.json`. Only consulted when tooltip extraction gives low confidence or for non-combat entities (status effects, island features) that don't have an in-game panel.

AE filter: the wiki flags Advanced Edition content explicitly. Since we run AE, prefer AE sections.

**Steam forum + Reddit** are an automated third source, added 2026-04-20.

Fetched via `WebFetch` after the wiki returns. Confined to two queries per unknown — one Steam forum search, one `r/IntoTheBreach` search — both keyed on the unknown's canonical name. Community threads catch edge-case interactions and unintuitive behavior that the wiki sanitizes or omits.

Results attach to the same `data/wiki_raw/<Name>.json` record under a `community_notes` field: `[{source_url, excerpt, confidence}, ...]`. Confidence bands: `confirmed` (tooltip + wiki + forum agree), `likely` (tooltip + wiki), `speculative` (forum-only). Low-confidence notes (sparse, contradicted, joke threads) are dropped by the orchestrator before write.

Still manual: deep mechanics debates, speculative patch notes, version-divergence discussions — these need human judgment the automated step shouldn't fake.

### Disagreement resolution

When tooltip, wiki, and existing code disagree:

1. Tooltip wins for **this installed build** (authoritative observation).
2. Wiki wins for mechanics not visible in the tooltip (status effect durations, spawn rules, multi-turn behavior).
3. Code is never trusted — if it disagreed with reality, we'd never have detected a bug.

Log the disagreement to `data/research_disagreements.jsonl` for later review.

## Edge cases

1. **False-positive storm** — flaky bridge reads. Require 2 confirming reads before counting toward frequency thresholds.
2. **Soft-disable cage** — expiry rule plus strategic override plus floor (never disable all weapons of a mech simultaneously).
3. **Strategist-intentional suboptimal actions** — tag with `strategic_intent` so blocklist ignores them.
4. **Override regression** — a fix for mission X breaks mission Y. Gate overrides on a regression board.
5. **Wiki vs tooltip disagreement** — tooltip wins; log.
6. **Hidden modifiers** — Volatile Vek looks like regular Scorpion. Include mission-level flags in novelty check, not just unit type.
7. **Bridge gap category** — field in save file but not in bridge state. Detector runs save-parser in parallel and diffs keys.
8. **Game version drift** — AE vs vanilla. Tag every research artifact with version pulled from save file.
9. **Recursive discovery** — new unknown surfaced while researching a prior unknown. Dedup by `(type, terrain_id, weapon_id, screen_id)` tuple. The inline orchestrator holds a per-call in-flight set to block re-entry on the same target; nested novel terms encountered while researching X are appended to the run queue and picked up after X's record is written.
10. **User pauses / quits mid-research** — queue persists; resume on next session.
11. **Hot-patch safety** — never auto-commit overrides. PR-style review required.
12. **Tooltip occlusion** — attack preview / shield animation hides panel. Mouse-move to neutral tile first.
13. **Claude Vision miss** — small fonts, pixel art. Zoom 3–4× before reading; fall back to "asked-user" on low confidence.
14. **Multi-select / multiple enemies selected** — UI may show the wrong unit's panel. Click exactly one tile, verify the panel matches.
15. **Terminal states during research** — inline research can be interrupted by a terminal transition (`Region Secured`, defeat, crash). The orchestrator polls the bridge phase on each step boundary; on a terminal observation it aborts cleanly so the end-of-mission UI flow isn't blocked, and unfinished targets persist in the queue for the next mission or run.

## Phased tickets

### Phase 0 — instrumentation (zero behavior change)

- **#P0-1** Add `failure_events_this_run: list[dict]` to `RunSession` (+ serialization test).
- **#P0-2** Create `src/solver/fuzzy_detector.py` with stub `evaluate()` that returns classification as-is. Import from `cmd_auto_turn`.
- **#P0-3** Wire hook at `commands.py:2471`: append every signal to `session.failure_events_this_run` AND enrich the `failure_db.jsonl` record with a new `fuzzy_signal` field.
- **#P0-4** Create `data/known_types.json` generated from `data/wiki_raw/` filenames + Rust weapon/enemy enums. Add a tiny script under `scripts/regenerate_known_types.py`.
- **#P0-5** `cmd_read` emits `unknowns: [...]` when a type/terrain_id is outside the known set.

**Exit criteria:** regression green; at least one real run recorded with `failure_events_this_run` populated and non-empty `fuzzy_signal` fields on existing desyncs.

### Phase 1 — passive response

- **#P1-1** Flesh out `evaluate()` logic: frequency window, diff topology check, asymmetry detection.
- **#P1-2** Add `disabled_actions` to `RunSession` with expiry rules.
- **#P1-3** Evaluator integration: pass blocklist into Rust solver (via JSON input); apply score bias on matching actions.
- **#P1-4** `auto_turn` result includes `fuzzy_detections`, `soft_disabled`, `unknowns_flagged`, `solver_gap_events`.
- **#P1-5** Narrator: terminal output prints each signal in human language.
- **#P1-6** Regression: re-run the full `failure_db.jsonl` corpus with the new detector; verify no solver regressions, log how many would have been soft-disabled.

**Exit criteria:** on a fresh run, at least one soft-disable fires correctly, doesn't cage the mech, and doesn't cause a mission loss that wouldn't have happened otherwise.

### Phase 2 — research pipeline + weapon-def regression harness

- **#P2-1** First ticket: **calibrate the three tooltip crop rectangles against this build.** Start the game, enter a mission, click one enemy, capture full screenshot, define `(x0, y0, x1, y1)` for name tag / UNIT STATUS / weapon preview. Write to `data/ui_regions.json`.
- **#P2-2** `research_queue` persisted on `RunSession`; between-turn processor pops one entry.
- **#P2-3** MCP sequence for tooltip capture: `mouse_move` neutral → `left_click` target → `screenshot` → three zoomed crops.
- **#P2-4** Claude Vision structured extraction (prompt templates per crop type).
- **#P2-5** Weapon-def comparator: given the extracted footprint / damage / push, diff against Rust `WeaponDef`. Write mismatches to `data/weapon_def_mismatches.jsonl`.
- **#P2-6** Fandom MediaWiki client (`src/research/wiki_client.py`); cache to `data/wiki_raw/`.
- **#P2-7** Status line in `auto_turn` output: `investigating: Scarab / Spitting_Glands` so the user sees progress without the game appearing frozen.

**Exit criteria:** a full run produces a `data/weapon_def_mismatches.jsonl` covering every weapon encountered, and zero false-positive mismatches (mismatches all correspond to real sim bugs).

### Phase 3 — active response (JSON weapon override)

- **#P3-1** Rust: `WeaponOverride` struct + `HashMap<u8, WeaponOverride>` param on `solve()`. Merge into lookup in `weapons.rs`.
- **#P3-2** Python caller passes overrides through. Wire from `weights/weapon_overrides.json`.
- **#P3-3** Mirror in `src/solver/simulate.py` for parity (dead code but keeps it honest).
- **#P3-4** Regression board gating: override entries require `tests/weapon_overrides/<weapon>_<case>.json`.

**Exit criteria:** one real override ships that fixes a previously-desync'd weapon behavior, demonstrated via regression diff.

### Phase 4 — auto-patch pipeline (shipped P4-1, P4-2)

- **#P4-1a** (shipped) `src/research/pattern_miner.py` — pure signature
  + mining function over the two jsonl corpora. Thresholds per source
  (Vision damage=1, Vision footprint/push=2, failure_db=3 boards).
  Deny-list consulted via signature hash.
- **#P4-1b** (shipped) `review_overrides reject` appends to
  `data/weapon_overrides_rejected.jsonl` so rejections persist across
  miner runs.
- **#P4-1c** (shipped) `src/research/board_extractor.py` —
  extract fixtures from recordings + observable-change verifier that
  mirrors the P3-7 regression gate.
- **#P4-1d** (shipped) `game_loop.py mine_overrides` CLI +
  `src/research/pr_drafter.py` — stacks the above into one dry-run
  report + ``--execute`` stage-to-disk flow. No branches, no auto-PRs
  yet; reuses the Phase 3 `review_overrides accept` path for promotion.
- **#P4-2** (shipped) Human review is enforced at four layers:
  review_overrides regression-board gate (P3-7), mine_overrides
  dry-run default, deny-list on reject, and explicit `git commit`
  after accept. No auto-commit to main on any path.

**Exit criteria:** the bot's first human-approved auto-drafted fix
— waiting on live Vision data with surviving mismatches. The P3-5
→ P3-6 path has been exercised (dc4b364 Cluster Artillery live-spin);
the P4-1 miner adds the cross-run pattern path that runs between
runs rather than inline on submit.

**Optional follow-ups (not scoped):**

- Auto-branch + `gh pr create --draft` once the staged-output quality
  is proven on live data.
- failure_db → override auto-generation. Needs a category→field map
  that doesn't exist yet; currently the drafter skips these.
- Per-weapon quota in the drafter cap (instead of absolute
  `--max-stage`) if one noisy weapon starts dominating the queue.

## Missing wire

Most subsystems are shipped (see **Status** at top). What's missing is the signal → action wiring and the coverage gaps the inline model exposes.

1. **Research gate (detection flag + protocol gate).** Python cannot drive `mcp__computer-use__*` tools directly — those are harness-side, which is why the orchestrator is already split into `begin_research` / `submit_research` around a Claude-dispatched MCP batch. A fully-blocking Python auto-dispatch is therefore not possible; the "inline" wire is detection-flag plus protocol-gate.
   - `cmd_read`: when `detect_unknowns` returns anything, set `result["requires_research"] = True` and print a loud banner. (Shipped in `src/loop/commands.py`.)
   - `cmd_solve` + `cmd_auto_turn`: early-return `{"error": "RESEARCH_REQUIRED", "unknowns": ..., "next": "cmd_research_next"}` when novelty is on the board. Helper: `src/solver/research_gate.py`. (Shipped.)
   - Protocol: CLAUDE.md rule 20 defines the harness sequence — `snapshot` → `research_next` → dispatch `plan.batch` via `computer_batch` → Vision per crop → `research_submit`, repeated until `NO_WORK`. Then combat resumes.
   - No Python call blocks on MCP; the orchestrator's two-step handshake does the moral equivalent across Claude's turn boundary.
2. **Weapon-id and screen-id coverage.** (Shipped 2026-04-20.) `unknown_detector.detect_unknowns(board, phase=None)` now returns four novelty axes: `types`, `terrain_ids`, `weapons`, and `screens`. Weapon coverage uses the Rust `WId` enum + underscore-stripped normalization (bridge form `Prime_Punchmech` reconciles to `PrimePunchmech`) plus an `observed_weapons` scan of recordings. Screen coverage is a phase-string registry (`combat_player`, `combat_enemy`, `between_missions`, `mission_ending`, `no_save`, `unknown`) sourced from `src/bridge/reader.py` and `src/capture/save_parser.py`; novel phase strings trip the gate. `research_gate_envelope` and `cmd_read` / `cmd_solve` handle all four axes. Deferred: a vision-based screen classifier for UI states the bridge phase string flattens to `combat_player` (shop, reward panels, CEO dialogs).
3. **Terrain + tile hover calibration.** Phase 2 `P2-1` calibrated unit tooltip crops only. Terrain tooltips hover on the tile itself and surface a different panel layout. Measure the crop region against this build; write to `data/ui_regions.json`.
4. **Forum/Reddit WebFetch step in `orchestrator.py`.** Slot it after the wiki lookup. Two queries per unknown; results attach to the wiki_raw record under `community_notes` with the confidence banding described in **External research**.
5. **Behavior-novelty route.** `fuzzy_detector` already tags unclassifiable desyncs. Extend the tag with the involved `unit.type` + `weapon_id`, and route the tag through the same orchestrator on the **next** `cmd_read` (not mid-sub-action — the one-action-per-desync verify contract stands).

Each item ships independently; order above is detection-first so the loop starts producing signal immediately, even before the forum step and behavior-novelty route land.

## Decisions summary

- Detection: structured signal pipeline, piggyback on `failure_db.jsonl`, wire at existing hook point.
- Response: Tier 1–4; Tier 3 JSON override mechanism shipped in Phase 3, auto-drafter in Phase 4.
- Tooltip: Claude Vision on small crops. Skip OCR.
- External research: Fandom MediaWiki API **plus** Steam forum + Reddit via WebFetch. [revised 2026-04-20]
- Research timing: **inline when an unknown is detected**, with deferred-queue fallback on failure. Mid-turn research IS a goal — ITB's turn-based nature makes the pause safe. [revised 2026-04-20]
- Weapon-def regression: pull out as an explicit v1 use case of Phase 2, not a v3 nice-to-have.
