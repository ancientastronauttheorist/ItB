"""Layer 2 of the desync diagnosis loop: rules-based root-cause proposal.

Given a ``failure_db.jsonl`` entry id, look up the action context from the
solve recording and try to match the diff against the rules table in
``diagnoses/rules.yaml``. On a unique dominant match, write a markdown
diagnosis under ``recordings/<run_id>/diagnoses/<failure_id>.md`` with
status ``rule_match``. On no match (or ambiguous match), write
``status=needs_agent`` markdown and stop — agent fallback is PR3.

Authoritative sim is the Rust crate at ``rust_solver/src/*.rs``.
``src/solver/simulate.py`` is test primitives only; no rule should
target it as a fix site.

Spec: docs/diagnosis_loop_design.md §7.
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


def find_failure(failure_id: str, db_path: Path = FAILURE_DB_PATH) -> dict | None:
    """Return the most recent failure_db record with matching id, or None.

    The id is constructed deterministically from (run_id, mission, turn,
    trigger, action_index) so the same id can recur across re-runs of
    verify_action. We pick the *last* matching line to reflect current
    state.
    """
    if not db_path.exists():
        return None
    last: dict | None = None
    with open(db_path) as f:
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


def diff_known_gap(diff: dict, gaps: list[dict] | None = None) -> str | None:
    """Return the id of the first known-gap that matches any diff entry."""
    if gaps is None:
        gaps = load_known_gaps()
    if not gaps:
        return None
    for ud in diff.get("unit_diffs", []):
        for gap in gaps:
            m = gap.get("match") or {}
            if m.get("diff_kind") not in (None, "unit_diff"):
                continue
            if "field" in m and ud.get("field") != m["field"]:
                continue
            if "predicted" in m and ud.get("predicted") != m["predicted"]:
                continue
            if "actual" in m and ud.get("actual") != m["actual"]:
                continue
            if not any(k in m for k in ("field", "predicted", "actual")):
                continue
            return gap.get("id")
    for td in diff.get("tile_diffs", []):
        for gap in gaps:
            m = gap.get("match") or {}
            if m.get("diff_kind") not in (None, "tile_diff"):
                continue
            if "field" in m and td.get("field") != m["field"]:
                continue
            if "predicted" in m and td.get("predicted") != m["predicted"]:
                continue
            if "actual" in m and td.get("actual") != m["actual"]:
                continue
            if not any(k in m for k in ("field", "predicted", "actual")):
                continue
            return gap.get("id")
    return None


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
) -> Path:
    """Render a diagnosis markdown for one failure_db entry.

    The frontmatter is YAML so future tooling (Layer 4 apply, INDEX.md
    generation) can parse it without re-deriving state. Body is plain
    markdown for easy GitHub rendering.
    """
    failure_id = failure.get("id", "unknown")
    run_id = failure.get("run_id", "default")
    if out_dir is None:
        out_dir = RECORDINGS_DIR / run_id / "diagnoses"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{failure_id}.md"

    sim_version = failure.get("simulator_version", 0)
    diff = failure.get("diff", {})

    if known_gap_id is not None:
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
    if known_gap_id is not None:
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
            "Multiple rules matched with equal specificity — manual review "
            "or agent fallback (PR3) needed to disambiguate."
        )
        body.append("")
        body.append("Candidates:")
        for r in match.candidates:
            first = r.hypothesis.splitlines()[0] if r.hypothesis else "?"
            body.append(f"  - `{r.id}` — {first}")
    else:
        body.append(
            "No seeded rule matched this diff signature. Agent fallback "
            "(PR3) would be invoked here once that layer ships. Until then, "
            "this diff needs human review."
        )
    body.append("")

    body.append("## Proposed fix")
    body.append("")
    if match.winner is not None and match.winner.proposed_fix:
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

    body.append("## Notes")
    body.append("")
    body.append(
        f"Generated by `game_loop.py diagnose {failure_id}` at "
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
) -> dict:
    """Top-level entry point used by ``cmd_diagnose`` and tests.

    ``failure`` and ``action`` may be supplied directly (test fixtures);
    otherwise they're loaded from failure_db.jsonl + the solve recording.
    Returns a result dict suitable for ``_print_result``.
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

    known_gap_id = None
    if not force:
        known_gap_id = diff_known_gap(diff)

    if known_gap_id is not None:
        match = MatchResult()
    else:
        match = match_rule(diff, action, sim_version, rules=rules)

    out_path = write_markdown(failure, action, match, known_gap_id, out_dir=out_dir)

    if known_gap_id is not None:
        status_label = "insufficient_data"
    elif match.winner is not None:
        status_label = "rule_match"
    else:
        status_label = "needs_agent"

    return {
        "status": status_label,
        "failure_id": failure_id,
        "rule_id": match.winner.id if match.winner else None,
        "candidates": [r.id for r in match.candidates],
        "ambiguous": match.ambiguous,
        "known_gap": known_gap_id,
        "confidence": match.winner.confidence if match.winner else "low",
        "markdown": str(out_path),
    }
