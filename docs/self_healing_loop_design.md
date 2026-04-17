# Self-Healing Loop Design

**Status:** proposal. Nothing is implemented yet.

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
  bridge read ────▶ │ unknown_detector → signals   │ ──▶ session.failure_events_this_run
                    │ fuzzy_detector → signals     │
                    │ (hook after classify_diff)   │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌────────── RESPONSE ───────────┐
                    │ Tier 1: re-solve (existing)   │
                    │ Tier 2: soft-disable action   │
                    │ Tier 3: JSON weapon override  │  ◀─── Phase 3 only
                    │ Tier 4: narrate, continue     │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────── RESEARCH (deferred) ───┐
                    │ tooltip capture (MCP + Vision)│
                    │ wiki.fandom API client         │
                    │ writes data/wiki_raw/<T>.json │
                    └───────────────────────────────┘
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

Runs between turns or between missions, never mid-turn (visual stall + recursion risk).

### Queue

`RunSession.research_queue` — list of `{type, terrain_id, mission_id, first_seen_turn, attempts}`. Deduped by `(type, terrain_id)`. Persists across sessions.

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

For **terrain** tooltips, hover is needed (different code path). Pixel region also TBD.

### External research (Fandom MediaWiki API)

```
GET https://intothebreach.fandom.com/api.php
  ?action=query&titles=<Name>&prop=wikitext&format=json
```

Cache to `data/wiki_raw/<Name>.json`. Only consulted when tooltip extraction gives low confidence or for non-combat entities (status effects, island features) that don't have an in-game panel.

AE filter: the wiki flags Advanced Edition content explicitly. Since we run AE, prefer AE sections.

Steam forum and community guides remain **manual-only** sources — used by humans when post-run analysis needs deeper mechanics clarification.

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
9. **Recursive discovery** — new unknown during research of previous unknown. Queue + dedup; never start research while another is in flight.
10. **User pauses / quits mid-research** — queue persists; resume on next session.
11. **Hot-patch safety** — never auto-commit overrides. PR-style review required.
12. **Tooltip occlusion** — attack preview / shield animation hides panel. Mouse-move to neutral tile first.
13. **Claude Vision miss** — small fonts, pixel art. Zoom 3–4× before reading; fall back to "asked-user" on low confidence.
14. **Multi-select / multiple enemies selected** — UI may show the wrong unit's panel. Click exactly one tile, verify the panel matches.
15. **Terminal states during research** — if research fires between turns and mission ends, abort research cleanly (don't block `Region Secured` flow).

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

### Phase 4 — auto-patch pipeline (optional, later)

- **#P4-1** Between-run script that turns `failure_db.jsonl` + `data/weapon_def_mismatches.jsonl` patterns into a draft PR (new override entry, new regression board).
- **#P4-2** Human review required before merge. Never auto-commit to main.

**Exit criteria:** the bot ships its first human-approved auto-drafted fix.

## Decisions summary

- Detection: structured signal pipeline, piggyback on `failure_db.jsonl`, wire at existing hook point.
- Response v1: Tier 1 (existing) + Tier 2 (soft-disable) + Tier 4 (narrate). Skip Tier 3 until measured need.
- Tooltip: Claude Vision on small crops. Skip OCR.
- External research: Fandom MediaWiki API only in v1. Forum stays manual.
- Research timing: deferred between turns. Mid-turn research is a non-goal.
- Weapon-def regression: pull out as an explicit v1 use case of Phase 2, not a v3 nice-to-have.
