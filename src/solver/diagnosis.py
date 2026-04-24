"""Layer 2 of the desync diagnosis loop: rules + agent fallback.

Given a ``failure_db.jsonl`` entry id:
  1. Consult ``diagnoses/rejections.jsonl`` — past rejected proposals never
     re-fire (signature × sim_version × proposed_fix_sig).
  2. Consult ``diagnoses/known_gaps.yaml`` — known model gaps short-circuit
     to ``status=insufficient_data`` unless ``--force``.
  3. Match the diff against ``diagnoses/rules.yaml``. Unique dominant match
     ⇒ ``status=rule_match`` markdown.
  4. No match ⇒ ``status=needs_agent``. Markdown carries the prompt the
     harness should hand to an Explore agent. The agent's JSON response is
     piped back in via ``cmd_diagnose_apply_agent`` (PR3 entry point), which
     validates path/line existence and ``target_language=rust`` before
     writing ``status=agent_proposed`` markdown.

Authoritative sim is the Rust crate at ``rust_solver/src/*.rs``.
``src/solver/simulate.py`` is test primitives only; agent responses
targeting it are rejected by the validator.

Spec: docs/diagnosis_loop_design.md §7 + §12.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.solver.verify import (
    _diff_signature,
    load_known_gaps,
    visual_coord,
)


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RULES_PATH = REPO_ROOT / "diagnoses" / "rules.yaml"
REJECTIONS_PATH = REPO_ROOT / "diagnoses" / "rejections.jsonl"
RECORDINGS_DIR = REPO_ROOT / "recordings"
FAILURE_DB_PATH = RECORDINGS_DIR / "failure_db.jsonl"


@dataclass
class Rule:
    """One row from diagnoses/rules.yaml.

    ``signature`` and ``discriminator`` together gate a match. Signature
    captures the diff shape we look for; discriminator captures the
    additional context (action's weapon, mech identity) that must hold
    to confidently attribute the diff to this rule's root cause.
    Match-on-symptom-only is a known foot-gun (design doc §13 #9).
    """

    id: str
    introduced_in_sim_version: int | None
    retired_in_sim_version: int | None
    signature: dict
    discriminator: dict
    confidence: str
    suspect_files: list[str]
    hypothesis: str
    proposed_fix: str

    def is_active(self, sim_version: int) -> bool:
        if (
            self.introduced_in_sim_version is not None
            and sim_version < self.introduced_in_sim_version
        ):
            return False
        if (
            self.retired_in_sim_version is not None
            and sim_version >= self.retired_in_sim_version
        ):
            return False
        return True


def load_rules(path: Path = RULES_PATH) -> list[Rule]:
    """Read diagnoses/rules.yaml. Empty list if missing or PyYAML absent."""
    if not path.exists():
        return []
    try:
        import yaml  # type: ignore
    except ImportError:
        return []
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return []
    out: list[Rule] = []
    for r in data.get("rules") or []:
        out.append(
            Rule(
                id=r["id"],
                introduced_in_sim_version=r.get("introduced_in_sim_version"),
                retired_in_sim_version=r.get("retired_in_sim_version"),
                signature=r.get("signature") or {},
                discriminator=r.get("discriminator") or {},
                confidence=r.get("confidence", "medium"),
                suspect_files=list(r.get("suspect_files") or []),
                hypothesis=r.get("hypothesis", ""),
                proposed_fix=r.get("proposed_fix", ""),
            )
        )
    return out


def find_failure(failure_id: str, db_path: Path | None = None) -> dict | None:
    """Return the most recent failure_db record with matching id, or None.

    The id is constructed deterministically from (run_id, mission, turn,
    trigger, action_index) so the same id can recur across re-runs of
    verify_action. We pick the *last* matching line to reflect current
    state. Path is resolved lazily so test fixtures can monkeypatch
    ``FAILURE_DB_PATH`` at the module level.
    """
    p = db_path if db_path is not None else FAILURE_DB_PATH
    if not p.exists():
        return None
    last: dict | None = None
    with open(p) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("id") == failure_id:
                last = rec
    return last


def load_action_for_failure(failure: dict) -> dict | None:
    """Look up the action that triggered this failure from the solve recording."""
    run_id = failure.get("run_id")
    mission = failure.get("mission")
    turn = failure.get("turn")
    action_index = failure.get("action_index")
    if not run_id or mission is None or turn is None or action_index is None:
        return None
    solve_path = (
        RECORDINGS_DIR
        / run_id
        / f"m{int(mission):02d}_turn_{int(turn):02d}_solve.json"
    )
    if not solve_path.exists():
        return None
    try:
        with open(solve_path) as f:
            rec = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    actions = (rec.get("data") or {}).get("actions") or []
    idx = int(action_index)
    if 0 <= idx < len(actions):
        return actions[idx]
    return None


def _matches_unit_diff_filter(
    filt: dict, unit_diffs: list[dict], actor_uid: int | None
) -> dict | None:
    """Return the first unit_diff entry matching all constraints in ``filt``.

    Recognised keys:
      field, predicted, actual                — exact match
      uid, type                               — exact match
      actor_only: true                        — uid must equal action.mech_uid
      actual_greater_than_predicted: true     — numeric pred < actual
      actual_less_than_predicted: true        — numeric pred > actual
      pos_shift_one_tile: true                — pred and actual differ by Manhattan-1
    """
    for ud in unit_diffs:
        if "field" in filt and ud.get("field") != filt["field"]:
            continue
        if "predicted" in filt and ud.get("predicted") != filt["predicted"]:
            continue
        if "actual" in filt and ud.get("actual") != filt["actual"]:
            continue
        if "type" in filt and ud.get("type") != filt["type"]:
            continue
        if "uid" in filt and ud.get("uid") != filt["uid"]:
            continue
        if filt.get("actor_only"):
            if actor_uid is None or ud.get("uid") != actor_uid:
                continue
        if filt.get("actual_greater_than_predicted"):
            try:
                if not (float(ud["actual"]) > float(ud["predicted"])):
                    continue
            except (TypeError, ValueError, KeyError):
                continue
        if filt.get("actual_less_than_predicted"):
            try:
                if not (float(ud["actual"]) < float(ud["predicted"])):
                    continue
            except (TypeError, ValueError, KeyError):
                continue
        if filt.get("pos_shift_one_tile"):
            pred = ud.get("predicted")
            actual = ud.get("actual")
            if not (
                isinstance(pred, list)
                and isinstance(actual, list)
                and len(pred) == 2
                and len(actual) == 2
            ):
                continue
            if abs(pred[0] - actual[0]) + abs(pred[1] - actual[1]) != 1:
                continue
        return ud
    return None


def _matches_tile_diff_filter(
    filt: dict, tile_diffs: list[dict], action: dict | None
) -> dict | None:
    """Return the first tile_diff entry matching all constraints in ``filt``."""
    target = (action or {}).get("target")
    target_xy = (
        (target[0], target[1])
        if isinstance(target, (list, tuple)) and len(target) >= 2
        else None
    )
    for td in tile_diffs:
        if "field" in filt and td.get("field") != filt["field"]:
            continue
        if "predicted" in filt and td.get("predicted") != filt["predicted"]:
            continue
        if "actual" in filt and td.get("actual") != filt["actual"]:
            continue
        if filt.get("at_action_target"):
            if target_xy is None or (td.get("x"), td.get("y")) != target_xy:
                continue
        return td
    return None


def _discriminator_holds(disc: dict, action: dict | None) -> bool:
    """Return True if the action satisfies the rule's discriminator clauses.

    Recognised keys:
      weapon_id_in:    [list of weapon_id strings]
      weapon_id_none:  bool — true ⇒ action has no weapon (move-only / Unknown)
      mech_type_in:    [list of mech_type strings]
    """
    if not disc:
        return True
    wid = ((action or {}).get("weapon_id") or "").strip()
    if "weapon_id_in" in disc:
        if wid not in disc["weapon_id_in"]:
            return False
    if "weapon_id_none" in disc:
        is_none = wid in ("", "Unknown", "None")
        if bool(disc["weapon_id_none"]) != is_none:
            return False
    if "mech_type_in" in disc:
        mt = (action or {}).get("mech_type") or ""
        if mt not in disc["mech_type_in"]:
            return False
    return True


def _signature_matches(
    sig: dict, diff: dict, action: dict | None
) -> tuple[bool, list[str]]:
    """Return (matches, evidence). evidence is a list of human-readable lines."""
    evidence: list[str] = []
    actor_uid = (action or {}).get("mech_uid")

    ud_filter = sig.get("unit_diff")
    if ud_filter:
        matched = _matches_unit_diff_filter(
            ud_filter, diff.get("unit_diffs", []), actor_uid
        )
        if matched is None:
            return False, []
        evidence.append(
            f"unit_diff: {matched.get('type', '?')} uid={matched.get('uid', '?')} "
            f"{matched.get('field', '?')} pred={matched.get('predicted')!r} "
            f"actual={matched.get('actual')!r}"
        )

    td_filter = sig.get("tile_diff")
    if td_filter:
        matched = _matches_tile_diff_filter(
            td_filter, diff.get("tile_diffs", []), action
        )
        if matched is None:
            return False, []
        x, y = matched.get("x", 0), matched.get("y", 0)
        evidence.append(
            f"tile_diff: {visual_coord(x, y)} ({x},{y}) "
            f"{matched.get('field', '?')} pred={matched.get('predicted')!r} "
            f"actual={matched.get('actual')!r}"
        )

    return True, evidence


def _specificity(rule: Rule) -> int:
    """Rough specificity score — more constraints ⇒ more specific."""
    n = 0
    for v in rule.signature.values():
        if isinstance(v, dict):
            n += 1 + sum(1 for vv in v.values() if vv is not None)
        elif v is not None:
            n += 1
    for v in rule.discriminator.values():
        if v is not None:
            n += 1
    return n


@dataclass
class MatchResult:
    """Outcome of matching one diff against the rules table."""

    winner: Rule | None = None
    evidence: list[str] = field(default_factory=list)
    candidates: list[Rule] = field(default_factory=list)
    ambiguous: bool = False


def match_rule(
    diff: dict,
    action: dict | None,
    sim_version: int,
    rules: list[Rule] | None = None,
) -> MatchResult:
    """Find the strictly dominant rule matching this diff, or none.

    Returns a MatchResult with winner=None when nothing matches OR when
    multiple rules tie at the top of the specificity ranking. Ambiguous
    ties become candidates for the agent fallback in PR3 — for now they
    surface as ``status=needs_agent`` markdown.
    """
    if rules is None:
        rules = load_rules()
    matched: list[tuple[Rule, list[str]]] = []
    for rule in rules:
        if not rule.is_active(sim_version):
            continue
        ok, evidence = _signature_matches(rule.signature, diff, action)
        if not ok:
            continue
        if not _discriminator_holds(rule.discriminator, action):
            continue
        matched.append((rule, evidence))
    if not matched:
        return MatchResult()

    matched.sort(key=lambda x: -_specificity(x[0]))
    top_rule, top_evidence = matched[0]
    if (
        len(matched) >= 2
        and _specificity(matched[0][0]) == _specificity(matched[1][0])
    ):
        return MatchResult(
            winner=None,
            evidence=[],
            candidates=[m[0] for m in matched],
            ambiguous=True,
        )
    return MatchResult(
        winner=top_rule,
        evidence=top_evidence,
        candidates=[m[0] for m in matched],
    )


def _match_gap_for_entry(
    entry: dict, kind: str, gaps: list[dict]
) -> str | None:
    """Return the id of the first known-gap matching this single diff entry."""
    for gap in gaps:
        m = gap.get("match") or {}
        if m.get("diff_kind") not in (None, kind):
            continue
        if "field" in m and entry.get("field") != m["field"]:
            continue
        if "predicted" in m and entry.get("predicted") != m["predicted"]:
            continue
        if "actual" in m and entry.get("actual") != m["actual"]:
            continue
        if not any(k in m for k in ("field", "predicted", "actual")):
            continue
        return gap.get("id")
    return None


def classify_diffs_against_gaps(
    diff: dict, gaps: list[dict] | None = None,
) -> tuple[int, int, str | None]:
    """Per-diff classification against known_gaps.yaml.

    Returns (gap_count, novel_count, sample_gap_id):
      - gap_count: number of diff entries that match some known gap
      - novel_count: entries that DON'T match any known gap
      - sample_gap_id: id of one matching gap (for the markdown body),
        or None when no diffs match a gap.

    Use this instead of the old all-or-nothing `diff_known_gap` so that
    a single gap-tagged diff doesn't suppress diagnosis on its 27 novel
    siblings (the bug surfaced when running the loop on turn 2 of run
    20260423_131700_144).
    """
    if gaps is None:
        gaps = load_known_gaps()
    gap_count = 0
    novel_count = 0
    sample: str | None = None
    if not gaps:
        novel_count = (
            len(diff.get("unit_diffs", []))
            + len(diff.get("tile_diffs", []))
            + len(diff.get("scalar_diffs", []))
        )
        return 0, novel_count, None
    for ud in diff.get("unit_diffs", []):
        gid = _match_gap_for_entry(ud, "unit_diff", gaps)
        if gid is not None:
            gap_count += 1
            sample = sample or gid
        else:
            novel_count += 1
    for td in diff.get("tile_diffs", []):
        gid = _match_gap_for_entry(td, "tile_diff", gaps)
        if gid is not None:
            gap_count += 1
            sample = sample or gid
        else:
            novel_count += 1
    # scalar_diffs aren't gap-matchable today; treat them as novel.
    novel_count += len(diff.get("scalar_diffs", []))
    return gap_count, novel_count, sample


def diff_known_gap(diff: dict, gaps: list[dict] | None = None) -> str | None:
    """Return a known-gap id IF every diff entry is gap-tagged, else None.

    Behavioural note: this used to return on the FIRST gap match — that
    short-circuited diagnose on a 28-diff record where 27 diffs were
    novel. New semantics: short-circuit only when there's nothing else
    worth diagnosing. Mixed records (some gap, some novel) flow into the
    rules engine + agent fallback as usual; the gap diffs are tagged in
    the verbose Layer 1 output but don't gate Layer 2.
    """
    gap_count, novel_count, sample = classify_diffs_against_gaps(diff, gaps)
    if novel_count > 0:
        return None
    if gap_count == 0:
        return None
    return sample


# ── Rejection store ────────────────────────────────────────────────────────
#
# A rejected proposal is keyed by (combined_diff_signature, sim_version,
# proposed_fix_sig). The first two come from the failure_db record; the
# third is a sha-of-fix-snippet so two different fixes for the same diff
# can each be rejected independently. Layer 2 short-circuits if the
# *combined_diff_signature × sim_version* pair has any matching rejection,
# regardless of fix_sig — once a human says "wrong direction", the loop
# shouldn't keep guessing variants of the same wrong fix.

import hashlib


def combined_diff_signature(diff: dict) -> str:
    """Stable hash of the entire diff, used as the rejection cache key.

    Order-insensitive within each diff bucket so diffs that fire in a
    different order across runs still dedupe. Truncated to 16 hex chars
    for human readability — collision probability is negligible at the
    failure_db scale (low thousands of records).
    """
    sigs = sorted(_diff_signatures(diff))
    payload = "\n".join(sigs)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def fix_signature(fix_snippet: dict | str | None) -> str:
    """Stable hash of an agent's proposed fix.

    Accepts either the raw {before, after} dict or a pre-serialized string.
    Empty / None ⇒ ``"none"`` so cache lookups don't false-positive on
    record_rejection invocations that have no fix attached.
    """
    if fix_snippet is None:
        return "none"
    if isinstance(fix_snippet, dict):
        before = (fix_snippet.get("before") or "").strip()
        after = (fix_snippet.get("after") or "").strip()
        if not before and not after:
            return "none"
        payload = f"{before}\n---\n{after}"
    else:
        payload = str(fix_snippet).strip()
        if not payload:
            return "none"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _rejections_path(path: Path | None) -> Path:
    """Resolve the rejections file path lazily.

    Defaulting the path argument at definition time captures the module-
    level REJECTIONS_PATH as it was at import — that breaks monkeypatching
    in tests. Resolve at call time so test fixtures can swap it.
    """
    if path is not None:
        return path
    return REJECTIONS_PATH


def _load_rejections(path: Path | None = None) -> list[dict]:
    p = _rejections_path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    with open(p) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def is_rejected(
    diff: dict,
    sim_version: int,
    fix_sig: str | None = None,
    rejections: list[dict] | None = None,
    path: Path | None = None,
) -> dict | None:
    """Return the matching rejection record, or None.

    A diff is considered rejected when *any* prior rejection shares its
    combined_diff_signature AND sim_version. If ``fix_sig`` is supplied,
    only the exact fix is gated (used by Layer 4 apply guard); else the
    diff-level guard fires.
    """
    if rejections is None:
        rejections = _load_rejections(path)
    if not rejections:
        return None
    target_sig = combined_diff_signature(diff)
    for rec in rejections:
        if rec.get("diff_signature") != target_sig:
            continue
        if rec.get("sim_version") != sim_version:
            continue
        if fix_sig is not None and rec.get("proposed_fix_sig") != fix_sig:
            continue
        return rec
    return None


def record_rejection(
    failure_id: str,
    reason: str,
    diff: dict,
    sim_version: int,
    proposed_fix: dict | str | None = None,
    path: Path | None = None,
) -> dict:
    """Append a rejection record to ``diagnoses/rejections.jsonl``.

    Idempotent on the (failure_id, fix_signature) pair — the same fix
    can't be rejected twice with the same reason. Returns the written
    record (or the existing one on dedup hit).
    """
    fix_sig = fix_signature(proposed_fix)
    diff_sig = combined_diff_signature(diff)

    p = _rejections_path(path)
    existing = _load_rejections(p)
    for rec in existing:
        if (
            rec.get("failure_id") == failure_id
            and rec.get("proposed_fix_sig") == fix_sig
        ):
            return rec

    record = {
        "failure_id": failure_id,
        "diff_signature": diff_sig,
        "sim_version": sim_version,
        "proposed_fix_sig": fix_sig,
        "reason": reason,
        "rejected_at": datetime.now(timezone.utc).isoformat(),
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as f:
        f.write(json.dumps(record) + "\n")
    return record


# ── Agent prompt + validator ──────────────────────────────────────────────


# Compact diff-category → suspect-file map. Embedded in the agent prompt
# so the agent knows where to start reading. Mirrors design doc Appendix A
# but trimmed — the agent does the precise file:line work itself.
_DIFF_CATEGORY_MAP = """
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
"""


def build_agent_prompt(
    failure: dict,
    action: dict | None,
    diff_block: str | None = None,
) -> str:
    """Compose the prompt the harness should hand to an Explore agent.

    Embeds the failure record, a Layer 1-style diff block, and the compact
    diff-category → suspect-file map. Pins Rust as authoritative and
    constrains the response to the strict JSON schema validate_agent_response
    enforces. Spec: design doc §7.2.
    """
    failure_for_prompt = {
        k: v
        for k, v in failure.items()
        if k in (
            "id", "run_id", "mission", "turn", "action_index", "mech_uid",
            "category", "subcategory", "severity", "details",
            "simulator_version", "solver_version", "diff",
        )
    }
    failure_json = json.dumps(failure_for_prompt, indent=2, default=str)
    action_json = json.dumps(action or {}, indent=2, default=str)
    diff_block = diff_block or "(no pretty-printed block; use diff JSON above)"

    return f"""You are diagnosing a simulator desync in an Into the Breach solver.

The Rust simulator at `rust_solver/src/` is AUTHORITATIVE. Files under
`src/solver/simulate.py` are TEST PRIMITIVES ONLY — never propose fixes
there. Responses with `target_language: python` are auto-rejected.

FAILURE RECORD (failure_db.jsonl entry):
```json
{failure_json}
```

TRIGGERING ACTION (from solve recording):
```json
{action_json}
```

DIFF DETAIL (Layer 1 pretty-printed):
```
{diff_block}
```

DIFF-CATEGORY → SUSPECT-FILE MAP (start here, expand as needed):
```
{_DIFF_CATEGORY_MAP.strip()}
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

{{
  "target_language": "rust",
  "root_cause": "one-paragraph hypothesis",
  "suspect_files": [
    {{"path": "rust_solver/src/simulate.rs", "lines": [START, END]}}
  ],
  "fix_snippet": {{
    "before": "...",
    "after":  "..."
  }},
  "confidence": "high|medium|low",
  "verification_plan": ["step 1", "step 2"],
  "open_questions": []
}}
"""


@dataclass
class AgentResponse:
    """Validated agent response, or a list of validation failures."""

    target_language: str
    root_cause: str
    suspect_files: list[dict]
    fix_snippet: dict
    confidence: str
    verification_plan: list[str]
    open_questions: list[str]
    raw: dict


def _parse_agent_json(payload: str | dict) -> tuple[dict | None, str | None]:
    """Extract a JSON object from an agent's response.

    The prompt asks for raw stdout, but real agents return prose around
    their JSON, multiple ```json fences, or both. We try in order:
      1. Parse the whole string verbatim.
      2. Strip a single leading ``` fence (one-shot fenced output).
      3. Find the last complete top-level {...} block by brace-balancing
         and parse that. Last-block-wins so when an agent thinks aloud
         then commits to a final answer, we honour the final one.
    Returns (dict, None) on success or (None, error_msg) on failure.
    """
    if isinstance(payload, dict):
        return payload, None
    if not isinstance(payload, str):
        return None, f"agent response must be str or dict, got {type(payload).__name__}"
    text = payload.strip()

    # Step 1: bare JSON.
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        pass

    # Step 2: fenced output — strip a single ``` wrapper.
    fenced = text
    if fenced.startswith("```"):
        first_nl = fenced.find("\n")
        if first_nl > 0:
            fenced = fenced[first_nl + 1 :]
            if fenced.rstrip().endswith("```"):
                fenced = fenced.rstrip()[:-3]
            try:
                return json.loads(fenced.strip()), None
            except json.JSONDecodeError:
                pass

    # Step 3: scan for top-level {...} blocks via brace-balancing.
    # Skip braces inside string literals (handles JSON strings that
    # contain '{' or '}' — Rust code snippets in fix_snippet do).
    blocks: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                blocks.append(text[start : i + 1])
                start = -1

    # Try each candidate block, last first — when the agent reasons aloud
    # and then finalizes, the final block is the answer.
    last_err = None
    for candidate in reversed(blocks):
        try:
            return json.loads(candidate), None
        except json.JSONDecodeError as e:
            last_err = e
            continue

    return None, f"invalid JSON: {last_err or 'no parseable {...} block found'}"


def validate_agent_response(
    payload: str | dict,
    repo_root: Path = REPO_ROOT,
) -> tuple[AgentResponse | None, list[str]]:
    """Parse + validate an agent's diagnosis JSON.

    Returns (AgentResponse, []) on success, or (None, [error, ...]) on
    failure. The validator enforces:
      - JSON parses (one tolerance: leading/trailing markdown fences)
      - target_language == "rust"
      - suspect_files is non-empty and every path resolves under repo_root
        (and never under src/solver/simulate.py — Python sim is test-only)
      - lines are integers within the file's actual line count
      - confidence ∈ {high, medium, low}
      - fix_snippet has both before + after (non-empty)
    """
    errors: list[str] = []

    parsed, err = _parse_agent_json(payload)
    if err is not None:
        return None, [err]
    assert parsed is not None

    target_language = parsed.get("target_language")
    if target_language != "rust":
        errors.append(
            f"target_language must be 'rust' (got {target_language!r}); "
            "src/solver/simulate.py is test-only — fixes go in rust_solver/"
        )

    confidence = parsed.get("confidence")
    if confidence not in ("high", "medium", "low"):
        errors.append(
            f"confidence must be one of high/medium/low (got {confidence!r})"
        )

    suspect_files = parsed.get("suspect_files") or []
    if not isinstance(suspect_files, list) or not suspect_files:
        errors.append("suspect_files must be a non-empty list")
        suspect_files = []

    for i, sf in enumerate(suspect_files):
        if not isinstance(sf, dict):
            errors.append(f"suspect_files[{i}] must be an object")
            continue
        path_str = sf.get("path") or ""
        if not path_str:
            errors.append(f"suspect_files[{i}] missing 'path'")
            continue
        if path_str.startswith("src/solver/simulate.py"):
            errors.append(
                f"suspect_files[{i}] targets src/solver/simulate.py — that's "
                "test primitives only. Propose Rust fixes."
            )
            continue
        if not (
            path_str.startswith("rust_solver/")
            or path_str.startswith("src/bridge/")
        ):
            errors.append(
                f"suspect_files[{i}] path {path_str!r} must live under "
                "rust_solver/ or src/bridge/ — Rust is authoritative."
            )
            continue
        full = repo_root / path_str
        if not full.exists():
            errors.append(
                f"suspect_files[{i}] path {path_str!r} does not exist"
            )
            continue
        try:
            with open(full) as f:
                line_count = sum(1 for _ in f)
        except OSError as e:
            errors.append(f"suspect_files[{i}] read failed: {e}")
            continue
        lines = sf.get("lines") or []
        if not isinstance(lines, list) or not lines:
            errors.append(
                f"suspect_files[{i}] lines must be a non-empty list of ints"
            )
            continue
        for lineno in lines:
            if not isinstance(lineno, int) or lineno < 1 or lineno > line_count:
                errors.append(
                    f"suspect_files[{i}] line {lineno!r} out of range for "
                    f"{path_str!r} (1..{line_count})"
                )

    fix_snippet = parsed.get("fix_snippet") or {}
    if not isinstance(fix_snippet, dict):
        errors.append("fix_snippet must be an object with before/after")
        fix_snippet = {}
    else:
        before = (fix_snippet.get("before") or "").strip()
        after = (fix_snippet.get("after") or "").strip()
        if not before or not after:
            errors.append(
                "fix_snippet.before and fix_snippet.after must both be non-empty"
            )

    if errors:
        return None, errors

    return (
        AgentResponse(
            target_language=parsed["target_language"],
            root_cause=str(parsed.get("root_cause") or ""),
            suspect_files=suspect_files,
            fix_snippet=fix_snippet,
            confidence=confidence,
            verification_plan=list(parsed.get("verification_plan") or []),
            open_questions=list(parsed.get("open_questions") or []),
            raw=parsed,
        ),
        [],
    )


def _format_unit_diff_md(ud: dict) -> str:
    return (
        f"  - {ud.get('type', '?')} (uid={ud.get('uid', '?')}) "
        f"`{ud.get('field', '?')}`: pred=`{ud.get('predicted')!r}` "
        f"actual=`{ud.get('actual')!r}`"
    )


def _format_tile_diff_md(td: dict) -> str:
    x = td.get("x", 0)
    y = td.get("y", 0)
    return (
        f"  - {visual_coord(x, y)} ({x},{y}) `{td.get('field', '?')}`: "
        f"pred=`{td.get('predicted')!r}` actual=`{td.get('actual')!r}`"
    )


def _proposed_files_yaml(suspect_files: list[str]) -> str:
    if not suspect_files:
        return "  []"
    lines = []
    for sf in suspect_files:
        if ":" in sf:
            path, line = sf.split(":", 1)
            lines.append(f"  - path: {path}")
            lines.append(f"    lines: [{line}]")
        else:
            lines.append(f"  - path: {sf}")
            lines.append(f"    lines: []")
    return "\n".join(lines)


def _diff_signatures(diff: dict) -> list[str]:
    sigs: list[str] = []
    for ud in diff.get("unit_diffs", []):
        sigs.append(_diff_signature("unit_diff", ud))
    for td in diff.get("tile_diffs", []):
        sigs.append(_diff_signature("tile_diff", td))
    for sd in diff.get("scalar_diffs", []):
        sigs.append(_diff_signature("scalar_diff", sd))
    return sigs


def write_markdown(
    failure: dict,
    action: dict | None,
    match: MatchResult,
    known_gap_id: str | None,
    out_dir: Path | None = None,
    rejection: dict | None = None,
    agent_prompt: str | None = None,
) -> Path:
    """Render a diagnosis markdown for one failure_db entry.

    The frontmatter is YAML so future tooling (Layer 4 apply, INDEX.md
    generation) can parse it without re-deriving state. Body is plain
    markdown for easy GitHub rendering.

    ``rejection`` short-circuits the body with a ``status=rejected`` block
    citing the prior rejection record. ``agent_prompt`` embeds the
    PR3 agent prompt block under needs_agent so the harness can copy it
    straight to an Agent dispatch.
    """
    failure_id = failure.get("id", "unknown")
    run_id = failure.get("run_id", "default")
    if out_dir is None:
        out_dir = RECORDINGS_DIR / run_id / "diagnoses"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{failure_id}.md"

    sim_version = failure.get("simulator_version", 0)
    diff = failure.get("diff", {})

    if rejection is not None:
        status = "rejected"
        confidence = "low"
    elif known_gap_id is not None:
        status = "insufficient_data"
        confidence = "low"
    elif match.winner is not None:
        status = "rule_match"
        confidence = match.winner.confidence
    elif match.ambiguous:
        status = "needs_agent"
        confidence = "low"
    else:
        status = "needs_agent"
        confidence = "low"

    suspect_files = match.winner.suspect_files if match.winner else []
    rules_matched_lines = []
    if match.winner is not None:
        rules_matched_lines.append(f"  - {match.winner.id}")
    elif match.candidates:
        for r in match.candidates:
            rules_matched_lines.append(f"  - {r.id}")
    else:
        rules_matched_lines.append("  []")
    rules_matched_yaml = "\n".join(rules_matched_lines)

    diff_sigs = _diff_signatures(diff)
    diff_sigs_yaml = (
        "\n".join(f"  - \"{s}\"" for s in diff_sigs) if diff_sigs else "  []"
    )

    frontmatter = "\n".join(
        [
            "---",
            f"id: {failure_id}",
            f"failure_id: {failure_id}",
            f"run_id: {run_id}",
            f"mission: {failure.get('mission', 0)}",
            f"turn: {failure.get('turn', 0)}",
            f"action_index: {failure.get('action_index', 'null')}",
            f"sim_version_at_diagnosis: {sim_version}",
            f"status: {status}",
            f"confidence: {confidence}",
            "applied_in_commit: null",
            "retired_in_sim_version: null",
            "duplicates_of: null",
            "target_language: rust",
            "proposed_files:",
            _proposed_files_yaml(suspect_files),
            "rules_matched:",
            rules_matched_yaml,
            "agent_invoked: false",
            "agent_tokens: 0",
            "diff_signatures:",
            diff_sigs_yaml,
            "---",
            "",
        ]
    )

    body: list[str] = []
    body.append("## Symptom")
    body.append("")
    if action:
        body.append(f"- Action: {action.get('description', '?')}")
        body.append(
            f"- Mech: {action.get('mech_type', '?')} (uid={action.get('mech_uid', '?')})"
        )
        if action.get("weapon"):
            wid = action.get("weapon_id")
            wid_part = f" (id=`{wid}`)" if wid else ""
            body.append(f"- Weapon: {action['weapon']}{wid_part}")
        target = action.get("target")
        if (
            isinstance(target, (list, tuple))
            and len(target) >= 2
            and tuple(target[:2]) != (255, 255)
        ):
            tx, ty = target[0], target[1]
            body.append(f"- Target: {visual_coord(tx, ty)} ({tx},{ty})")
        body.append("")
    body.append("Unit diffs:")
    if diff.get("unit_diffs"):
        for ud in diff["unit_diffs"]:
            body.append(_format_unit_diff_md(ud))
    else:
        body.append("  (none)")
    body.append("")
    body.append("Tile diffs:")
    if diff.get("tile_diffs"):
        for td in diff["tile_diffs"]:
            body.append(_format_tile_diff_md(td))
    else:
        body.append("  (none)")
    body.append("")
    body.append("Scalar diffs:")
    if diff.get("scalar_diffs"):
        for sd in diff["scalar_diffs"]:
            body.append(
                f"  - `{sd.get('field', '?')}`: "
                f"pred=`{sd.get('predicted')!r}` actual=`{sd.get('actual')!r}`"
            )
    else:
        body.append("  (none)")
    body.append("")

    body.append("## Hypothesis")
    body.append("")
    if rejection is not None:
        body.append(
            f"Previously rejected for this (diff_signature × sim_version)."
        )
        body.append("")
        body.append(f"- Rejected at: {rejection.get('rejected_at', '?')}")
        body.append(f"- Reason: {rejection.get('reason', '?')}")
        body.append(
            f"- diff_signature: `{rejection.get('diff_signature', '?')}`"
        )
        body.append(
            f"- proposed_fix_sig: `{rejection.get('proposed_fix_sig', '?')}`"
        )
        body.append("")
        body.append(
            "Bypass with `--force` to re-attempt the loop — but consider "
            "whether the rejection reason still applies first."
        )
    elif known_gap_id is not None:
        body.append(
            f"Diff matches known model gap `{known_gap_id}`. "
            "No simulator fix expected; tagged for tuner suppression. "
            "Re-run with `--force` to attempt rule matching anyway."
        )
    elif match.winner is not None:
        body.append(match.winner.hypothesis or "(no hypothesis text)")
        if match.evidence:
            body.append("")
            body.append("Match evidence:")
            for e in match.evidence:
                body.append(f"  - {e}")
    elif match.ambiguous:
        body.append(
            "Multiple rules matched with equal specificity — agent "
            "fallback (`game_loop.py diagnose_apply_agent`) or human review "
            "needed to disambiguate."
        )
        body.append("")
        body.append("Candidates:")
        for r in match.candidates:
            first = r.hypothesis.splitlines()[0] if r.hypothesis else "?"
            body.append(f"  - `{r.id}` — {first}")
    else:
        body.append(
            "No seeded rule matched this diff signature. The Layer 2 agent "
            "fallback prompt is below — dispatch it via the harness's Agent "
            "tool, then pipe the JSON response back through "
            "`game_loop.py diagnose_apply_agent <failure_id> '<json>'`."
        )
    body.append("")

    body.append("## Proposed fix")
    body.append("")
    if rejection is not None:
        body.append("(see Hypothesis — proposal rejected)")
    elif match.winner is not None and match.winner.proposed_fix:
        body.append("```")
        body.append(match.winner.proposed_fix)
        body.append("```")
    elif match.winner is not None:
        body.append(
            "(rule has no fix snippet — see suspect_files for the line range)"
        )
    else:
        body.append("(none — needs agent)")
    body.append("")

    body.append("## Verification plan")
    body.append("")
    body.append("- `bash scripts/regression.sh` (Rust + Python corpus)")
    if match.winner is not None:
        body.append(
            f"- `python3 game_loop.py replay {run_id} {failure.get('turn', 0)}` "
            "to confirm the fixed simulator reproduces the actual state"
        )
    body.append("")

    if (
        agent_prompt is not None
        and rejection is None
        and match.winner is None
        and known_gap_id is None
    ):
        body.append("## Agent prompt")
        body.append("")
        body.append("Dispatch this prompt via the harness's Explore agent. ")
        body.append(
            "When the agent returns its JSON, run "
            f"`python3 game_loop.py diagnose_apply_agent {failure_id} "
            "'<json>'` to validate + write the agent_proposed markdown."
        )
        body.append("")
        body.append("```")
        body.append(agent_prompt.strip())
        body.append("```")
        body.append("")

    body.append("## Notes")
    body.append("")
    body.append(
        f"Generated by `game_loop.py diagnose {failure_id}` at "
        f"{datetime.now(timezone.utc).isoformat()}."
    )
    body.append("")

    out_path.write_text(frontmatter + "\n".join(body))
    return out_path


def write_agent_proposed_markdown(
    failure: dict,
    action: dict | None,
    response: AgentResponse,
    out_dir: Path | None = None,
) -> Path:
    """Write a status=agent_proposed markdown for a validated agent response.

    Frontmatter mirrors the rule_match shape so Layer 4 can read either
    interchangeably. ``proposed_files`` and ``rules_matched`` are populated
    from the agent's structured output rather than the rules table.
    """
    failure_id = failure.get("id", "unknown")
    run_id = failure.get("run_id", "default")
    if out_dir is None:
        out_dir = RECORDINGS_DIR / run_id / "diagnoses"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{failure_id}.md"

    sim_version = failure.get("simulator_version", 0)
    diff = failure.get("diff", {})

    proposed_files_lines: list[str] = []
    for sf in response.suspect_files:
        proposed_files_lines.append(f"  - path: {sf.get('path')}")
        lines = sf.get("lines") or []
        proposed_files_lines.append(
            "    lines: [" + ", ".join(str(int(x)) for x in lines) + "]"
        )
    proposed_files_yaml = (
        "\n".join(proposed_files_lines) if proposed_files_lines else "  []"
    )

    diff_sigs = _diff_signatures(diff)
    diff_sigs_yaml = (
        "\n".join(f"  - \"{s}\"" for s in diff_sigs) if diff_sigs else "  []"
    )

    # Embed the fix snippet structurally so apply_diagnosis (Layer 4) can
    # parse it back unambiguously instead of reverse-engineering the body.
    # YAML literal block scalars preserve newlines + indentation.
    def _yaml_block(text: str) -> list[str]:
        text = text.rstrip("\n")
        return ["    " + line for line in text.split("\n")]

    fix_yaml_lines: list[str] = ["fix_snippet:"]
    fix_yaml_lines.append("  before: |")
    fix_yaml_lines.extend(_yaml_block(response.fix_snippet.get("before", "")))
    fix_yaml_lines.append("  after: |")
    fix_yaml_lines.extend(_yaml_block(response.fix_snippet.get("after", "")))

    frontmatter = "\n".join(
        [
            "---",
            f"id: {failure_id}",
            f"failure_id: {failure_id}",
            f"run_id: {run_id}",
            f"mission: {failure.get('mission', 0)}",
            f"turn: {failure.get('turn', 0)}",
            f"action_index: {failure.get('action_index', 'null')}",
            f"sim_version_at_diagnosis: {sim_version}",
            "status: agent_proposed",
            f"confidence: {response.confidence}",
            "applied_in_commit: null",
            "applied_at: null",
            "retired_in_sim_version: null",
            "duplicates_of: null",
            f"target_language: {response.target_language}",
            "proposed_files:",
            proposed_files_yaml,
            "rules_matched:",
            "  []",
            "agent_invoked: true",
            "agent_tokens: 0",
            f"proposed_fix_sig: \"{fix_signature(response.fix_snippet)}\"",
            *fix_yaml_lines,
            "diff_signatures:",
            diff_sigs_yaml,
            "---",
            "",
        ]
    )

    body: list[str] = []
    body.append("## Symptom")
    body.append("")
    if action:
        body.append(f"- Action: {action.get('description', '?')}")
        body.append(
            f"- Mech: {action.get('mech_type', '?')} (uid={action.get('mech_uid', '?')})"
        )
        if action.get("weapon"):
            wid = action.get("weapon_id")
            wid_part = f" (id=`{wid}`)" if wid else ""
            body.append(f"- Weapon: {action['weapon']}{wid_part}")
        target = action.get("target")
        if (
            isinstance(target, (list, tuple))
            and len(target) >= 2
            and tuple(target[:2]) != (255, 255)
        ):
            tx, ty = target[0], target[1]
            body.append(f"- Target: {visual_coord(tx, ty)} ({tx},{ty})")
        body.append("")
    body.append("Unit diffs:")
    if diff.get("unit_diffs"):
        for ud in diff["unit_diffs"]:
            body.append(_format_unit_diff_md(ud))
    else:
        body.append("  (none)")
    body.append("")
    body.append("Tile diffs:")
    if diff.get("tile_diffs"):
        for td in diff["tile_diffs"]:
            body.append(_format_tile_diff_md(td))
    else:
        body.append("  (none)")
    body.append("")
    body.append("Scalar diffs:")
    if diff.get("scalar_diffs"):
        for sd in diff["scalar_diffs"]:
            body.append(
                f"  - `{sd.get('field', '?')}`: "
                f"pred=`{sd.get('predicted')!r}` actual=`{sd.get('actual')!r}`"
            )
    else:
        body.append("  (none)")
    body.append("")

    body.append("## Hypothesis")
    body.append("")
    body.append(response.root_cause or "(agent provided no root_cause text)")
    body.append("")

    body.append("## Proposed fix")
    body.append("")
    body.append(f"Confidence: **{response.confidence}**")
    body.append("")
    if response.suspect_files:
        body.append("Suspect files:")
        for sf in response.suspect_files:
            lines = sf.get("lines") or []
            body.append(
                f"  - `{sf.get('path')}` lines "
                f"[{', '.join(str(int(x)) for x in lines)}]"
            )
        body.append("")
    body.append("```diff")
    body.append("// BEFORE:")
    body.append(response.fix_snippet.get("before", "").rstrip())
    body.append("// AFTER:")
    body.append(response.fix_snippet.get("after", "").rstrip())
    body.append("```")
    body.append("")

    body.append("## Verification plan")
    body.append("")
    body.append("- `bash scripts/regression.sh` (Rust + Python corpus)")
    if response.verification_plan:
        for step in response.verification_plan:
            body.append(f"- {step}")
    body.append(
        f"- `python3 game_loop.py replay {run_id} {failure.get('turn', 0)}` "
        "to confirm the fixed simulator reproduces the actual state"
    )
    body.append("")

    if response.open_questions:
        body.append("## Open questions")
        body.append("")
        for q in response.open_questions:
            body.append(f"- {q}")
        body.append("")

    body.append("## Notes")
    body.append("")
    body.append(
        "If this proposal is wrong, run "
        f"`python3 game_loop.py reject_diagnosis {failure_id} "
        "--reason \"...\"` to suppress it from future diagnose runs "
        "(diagnoses/rejections.jsonl)."
    )
    body.append("")
    body.append(
        f"Generated by agent fallback at "
        f"{datetime.now(timezone.utc).isoformat()}."
    )
    body.append("")

    out_path.write_text(frontmatter + "\n".join(body))
    return out_path


def diagnose(
    failure_id: str,
    force: bool = False,
    out_dir: Path | None = None,
    rules: list[Rule] | None = None,
    failure: dict | None = None,
    action: dict | None = None,
    emit_prompt: bool = True,
) -> dict:
    """Top-level entry point used by ``cmd_diagnose`` and tests.

    Resolution order: rejections → known_gaps → rules → needs_agent.
    ``--force`` skips both the rejections check and the known_gaps check
    so the loop will retry a previously-rejected diff. ``emit_prompt``
    controls whether the needs_agent markdown embeds the agent prompt
    block (set False in unit tests that just want the status).

    ``failure`` and ``action`` may be supplied directly (test fixtures);
    otherwise they're loaded from failure_db.jsonl + the solve recording.
    """
    if failure is None:
        failure = find_failure(failure_id)
    if failure is None:
        return {
            "status": "ERROR",
            "error": f"failure_id {failure_id!r} not found in failure_db.jsonl",
        }

    if action is None:
        action = load_action_for_failure(failure)

    sim_version = failure.get("simulator_version", 0)
    diff = failure.get("diff", {})

    rejection = None
    if not force:
        rejection = is_rejected(diff, sim_version)

    known_gap_id = None
    if rejection is None and not force:
        known_gap_id = diff_known_gap(diff)

    if rejection is not None or known_gap_id is not None:
        match = MatchResult()
    else:
        match = match_rule(diff, action, sim_version, rules=rules)

    agent_prompt = None
    if (
        emit_prompt
        and rejection is None
        and known_gap_id is None
        and match.winner is None
    ):
        agent_prompt = build_agent_prompt(failure, action)

    out_path = write_markdown(
        failure, action, match, known_gap_id,
        out_dir=out_dir, rejection=rejection, agent_prompt=agent_prompt,
    )

    if rejection is not None:
        status_label = "rejected"
    elif known_gap_id is not None:
        status_label = "insufficient_data"
    elif match.winner is not None:
        status_label = "rule_match"
    else:
        status_label = "needs_agent"

    result = {
        "status": status_label,
        "failure_id": failure_id,
        "rule_id": match.winner.id if match.winner else None,
        "candidates": [r.id for r in match.candidates],
        "ambiguous": match.ambiguous,
        "known_gap": known_gap_id,
        "rejection": rejection,
        "confidence": match.winner.confidence if match.winner else "low",
        "markdown": str(out_path),
    }
    if agent_prompt is not None:
        result["agent_prompt"] = agent_prompt
        result["next_step"] = (
            f"Dispatch the agent_prompt via Agent tool, then "
            f"`python3 game_loop.py diagnose_apply_agent {failure_id} '<json>'`"
        )
    return result


def apply_agent_response(
    failure_id: str,
    payload: str | dict,
    out_dir: Path | None = None,
    failure: dict | None = None,
    action: dict | None = None,
) -> dict:
    """Validate an agent's JSON response and write status=agent_proposed markdown.

    Returns a result dict; on validation failure ``status=ERROR`` and
    ``errors`` carries the per-clause failure list. The same payload is
    NOT auto-rejected — the harness can fix the JSON and re-submit.
    """
    if failure is None:
        failure = find_failure(failure_id)
    if failure is None:
        return {
            "status": "ERROR",
            "error": f"failure_id {failure_id!r} not found in failure_db.jsonl",
        }

    response, errors = validate_agent_response(payload)
    if response is None:
        return {
            "status": "ERROR",
            "failure_id": failure_id,
            "error": "agent response failed validation",
            "errors": errors,
        }

    if action is None:
        action = load_action_for_failure(failure)

    md_path = write_agent_proposed_markdown(failure, action, response, out_dir=out_dir)
    return {
        "status": "agent_proposed",
        "failure_id": failure_id,
        "confidence": response.confidence,
        "suspect_files": response.suspect_files,
        "fix_signature": fix_signature(response.fix_snippet),
        "markdown": str(md_path),
    }


def reject(
    failure_id: str,
    reason: str,
    failure: dict | None = None,
    proposed_fix: dict | str | None = None,
    out_dir: Path | None = None,
) -> dict:
    """Record a rejection + rewrite the markdown to status=rejected.

    Public entry point for ``cmd_reject_diagnosis`` and tests. The
    rejection record carries the diff_signature so future diagnose
    invocations can short-circuit on the same diff shape (within the
    same sim_version).
    """
    if failure is None:
        failure = find_failure(failure_id)
    if failure is None:
        return {
            "status": "ERROR",
            "error": f"failure_id {failure_id!r} not found in failure_db.jsonl",
        }
    if not reason or not reason.strip():
        return {
            "status": "ERROR",
            "error": "--reason is required (one-line explanation of why the proposal is wrong)",
        }

    diff = failure.get("diff", {})
    sim_version = failure.get("simulator_version", 0)

    rec = record_rejection(
        failure_id=failure_id,
        reason=reason.strip(),
        diff=diff,
        sim_version=sim_version,
        proposed_fix=proposed_fix,
    )

    action = load_action_for_failure(failure)
    md_path = write_markdown(
        failure, action, MatchResult(), None,
        out_dir=out_dir, rejection=rec, agent_prompt=None,
    )
    return {
        "status": "rejected",
        "failure_id": failure_id,
        "diff_signature": rec["diff_signature"],
        "proposed_fix_sig": rec["proposed_fix_sig"],
        "rejected_at": rec["rejected_at"],
        "markdown": str(md_path),
    }
