"""Layer 4 of the desync diagnosis loop: apply a diagnosis proposal.

`game_loop.py apply_diagnosis <id>` takes the agent_proposed markdown that
Layer 2 wrote and walks it through the strict apply sequence:

  1. Parse YAML frontmatter — verify status=agent_proposed (rule_match
     fixes are conceptual, not Edit-applicable; refused with a hint).
  2. Verify no uncommitted diff in any suspect_files target — refuse if
     the working tree would clobber user work (design doc §13 #28).
  3. Snapshot every target file in memory for revert.
  4. Apply the fix_snippet (before → after replacement, exact match).
  5. If any sim file changed (rust_solver/src/*.rs, src/solver/verify.py),
     atomically bump SIMULATOR_VERSION in BOTH lib.rs and verify.py and
     archive recordings/failure_db.jsonl to
     recordings/failure_db_snapshot_sim_v<old>.jsonl.
  6. --dry-run stops here with the plan.
  7. Rebuild Rust (`maturin build --release` + pip install of the wheel).
  8. Run scripts/regression.sh (Rust corpus + Python corpus).
  9. On any failure: revert every edit, restore the failure_db snapshot,
     mark the diagnosis status=apply_failed, exit non-zero.
 10. On success: rewrite the markdown frontmatter to status=applied
     (commit + push are user-driven; no auto-commit by default).

Spec: docs/diagnosis_loop_design.md §11 + §13 (#23-#29).
Memory note: feedback_simulator_version_atomic_bump.md — both files
must bump together; partial bump leaves a corpus inconsistency.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.solver.diagnosis import REPO_ROOT, RECORDINGS_DIR, find_failure


SIM_FILE_PREFIXES: tuple[str, ...] = (
    "rust_solver/src/",
    "src/solver/verify.py",
)
PYTHON_SIM_BLOCKLIST: str = "src/solver/simulate.py"

VERSION_FILE_RUST = REPO_ROOT / "rust_solver" / "src" / "lib.rs"
VERSION_FILE_PY = REPO_ROOT / "src" / "solver" / "verify.py"
FAILURE_DB_PATH = REPO_ROOT / "recordings" / "failure_db.jsonl"


# ── Markdown frontmatter parser ────────────────────────────────────────────


def parse_frontmatter(md_text: str) -> tuple[dict, str]:
    """Split a diagnosis markdown into (frontmatter_dict, body).

    Returns ({}, full_text) when no frontmatter is present so callers can
    fail gracefully instead of crashing on legacy markdown.
    """
    if not md_text.startswith("---"):
        return {}, md_text
    end = md_text.find("\n---", 3)
    if end < 0:
        return {}, md_text
    yaml_block = md_text[3:end].lstrip("\n")
    body = md_text[end + 4 :].lstrip("\n")
    try:
        import yaml  # type: ignore
        fm = yaml.safe_load(yaml_block) or {}
    except Exception:
        fm = {}
    return fm, body


def find_diagnosis_path(failure_id: str) -> Path | None:
    """Locate the markdown file for a given failure_id.

    Tries to derive run_id from the conventional id format
    `<run_id>_m<MM>_t<TT>_<trigger>_a<idx>` first; falls back to a glob
    over recordings/*/diagnoses/ when the id was synthesized.
    """
    diagnoses_root = RECORDINGS_DIR
    # Conventional layout: recordings/<run_id>/diagnoses/<failure_id>.md
    failure = find_failure(failure_id)
    if failure is not None:
        run_id = failure.get("run_id")
        if run_id:
            candidate = diagnoses_root / run_id / "diagnoses" / f"{failure_id}.md"
            if candidate.exists():
                return candidate
    # Fallback: scan all per-run dirs.
    for md in diagnoses_root.glob("*/diagnoses/*.md"):
        if md.stem == failure_id:
            return md
    return None


# ── Plan + outcome dataclasses ─────────────────────────────────────────────


@dataclass
class ApplyPlan:
    """What apply_diagnosis intends to do, before doing any of it."""

    failure_id: str
    diagnosis_path: Path
    status: str
    confidence: str
    target_language: str
    suspect_files: list[dict] = field(default_factory=list)
    fix_snippet: dict = field(default_factory=dict)
    needs_sim_bump: bool = False
    sim_version_before: int | None = None

    @property
    def edit_paths(self) -> list[Path]:
        return [
            REPO_ROOT / sf["path"]
            for sf in self.suspect_files
            if sf.get("path")
        ]


@dataclass
class ApplyOutcome:
    """Result of an apply attempt — captures what changed + how to revert."""

    status: str  # planned | applied | dry_run | apply_failed | refused
    plan: ApplyPlan | None
    edits: dict[Path, str] = field(default_factory=dict)
    archived_failure_db: Path | None = None
    sim_bumped: bool = False
    error: str | None = None
    stage: str | None = None  # which step failed


# ── Plan construction ──────────────────────────────────────────────────────


def _is_sim_file(rel_path: str) -> bool:
    return any(rel_path.startswith(p) for p in SIM_FILE_PREFIXES)


def build_apply_plan(failure_id: str,
                     diagnosis_path: Path | None = None) -> ApplyPlan | dict:
    """Parse the markdown + return a plan, or a dict-shaped error.

    Returning ApplyPlan on success and dict on error keeps the callers'
    type discrimination cheap (`isinstance(plan, dict)`). The plan is
    pure-data — no side effects until the caller runs through the apply
    sequence.
    """
    if diagnosis_path is None:
        diagnosis_path = find_diagnosis_path(failure_id)
    if diagnosis_path is None or not diagnosis_path.exists():
        return {
            "status": "ERROR",
            "error": (
                f"diagnosis markdown for {failure_id!r} not found under "
                f"recordings/<run_id>/diagnoses/"
            ),
        }
    text = diagnosis_path.read_text()
    fm, _body = parse_frontmatter(text)
    if not fm:
        return {
            "status": "ERROR",
            "error": f"{diagnosis_path} has no parseable YAML frontmatter",
        }

    status = fm.get("status")
    if status == "rule_match":
        return {
            "status": "ERROR",
            "error": (
                "rule_match proposals are conceptual hints, not Edit-applicable. "
                "Apply the suspect_files / proposed_fix manually, run regression, "
                "then bump SIMULATOR_VERSION yourself. apply_diagnosis only "
                "supports status=agent_proposed."
            ),
        }
    if status != "agent_proposed":
        return {
            "status": "ERROR",
            "error": (
                f"diagnosis status must be agent_proposed (got {status!r}); "
                "apply only fires on validated agent fixes"
            ),
        }

    target_language = fm.get("target_language") or ""
    if target_language != "rust":
        return {
            "status": "ERROR",
            "error": (
                f"target_language must be 'rust' (got {target_language!r}); "
                "Python sim is test-only — Rust is authoritative"
            ),
        }

    suspect_files = fm.get("proposed_files") or []
    if not isinstance(suspect_files, list) or not suspect_files:
        return {
            "status": "ERROR",
            "error": "frontmatter.proposed_files is empty — nothing to apply",
        }
    for sf in suspect_files:
        path_str = (sf or {}).get("path") or ""
        if path_str.startswith(PYTHON_SIM_BLOCKLIST):
            return {
                "status": "ERROR",
                "error": (
                    f"proposed_files contains {path_str!r} — Python sim is "
                    "test-only. Refusing to apply."
                ),
            }
        if not (REPO_ROOT / path_str).exists():
            return {
                "status": "ERROR",
                "error": f"proposed_files path {path_str!r} does not resolve",
            }

    fix_snippet = fm.get("fix_snippet") or {}
    before = (fix_snippet.get("before") or "").rstrip("\n")
    after = (fix_snippet.get("after") or "").rstrip("\n")
    if not before or not after:
        return {
            "status": "ERROR",
            "error": (
                "frontmatter.fix_snippet must have non-empty before + after — "
                "nothing to apply (re-run diagnose_apply_agent with a complete "
                "agent response)"
            ),
        }
    fix_snippet = {"before": before, "after": after}

    needs_sim_bump = any(
        _is_sim_file((sf or {}).get("path") or "") for sf in suspect_files
    )
    sim_version_before = read_sim_version_py() if needs_sim_bump else None

    return ApplyPlan(
        failure_id=failure_id,
        diagnosis_path=diagnosis_path,
        status=status,
        confidence=fm.get("confidence") or "low",
        target_language=target_language,
        suspect_files=suspect_files,
        fix_snippet=fix_snippet,
        needs_sim_bump=needs_sim_bump,
        sim_version_before=sim_version_before,
    )


# ── Working tree guard ─────────────────────────────────────────────────────


def dirty_targets(plan: ApplyPlan) -> list[str]:
    """Return paths in plan.edit_paths that have uncommitted changes.

    Also flags the SIMULATOR_VERSION files when a bump is required, so
    we don't accidentally land on top of a half-bumped version pair.
    """
    targets = list(plan.edit_paths)
    if plan.needs_sim_bump:
        targets += [VERSION_FILE_RUST, VERSION_FILE_PY]

    rel = []
    for p in targets:
        try:
            rel.append(str(p.relative_to(REPO_ROOT)))
        except ValueError:
            rel.append(str(p))

    if not rel:
        return []
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--", *rel],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return rel  # treat as dirty if git itself failed
    out = proc.stdout.strip()
    if not out:
        return []
    dirty = []
    for line in out.splitlines():
        # `git status --porcelain` lines: "XY <path>" with X+Y status
        # codes and a leading space when only the worktree changed.
        if len(line) > 3:
            dirty.append(line[3:].strip())
    return dirty


# ── Edit apply / revert ────────────────────────────────────────────────────


def apply_fix(plan: ApplyPlan) -> dict[Path, str]:
    """Apply the before→after replacement to every suspect_files target.

    Returns a dict of path → original_content for revert. Raises
    ValueError if the `before` block doesn't appear (unique) in a target.

    The matcher is intentionally strict: exact match including
    whitespace. Agent responses that hand-typed code with subtly
    different indentation than the file will fail loudly here.
    """
    before = plan.fix_snippet["before"]
    after = plan.fix_snippet["after"]
    originals: dict[Path, str] = {}
    matched = 0
    for sf in plan.suspect_files:
        rel = sf.get("path") or ""
        path = REPO_ROOT / rel
        text = path.read_text()
        count = text.count(before)
        if count == 0:
            continue  # try next target — agent may have cited multiple files
        if count > 1:
            raise ValueError(
                f"fix_snippet.before appears {count} times in {rel!r} — "
                "must be unique. Refine the snippet to include more context."
            )
        originals[path] = text
        path.write_text(text.replace(before, after))
        matched += 1
    if matched == 0:
        raise ValueError(
            "fix_snippet.before not found in any of the suspect_files. "
            "The agent's snippet doesn't match the live source — possibly "
            "the file moved since the diagnosis was generated."
        )
    return originals


def revert_fix(originals: dict[Path, str]) -> None:
    """Restore each captured file to its pre-apply content."""
    for path, text in originals.items():
        path.write_text(text)


# ── SIMULATOR_VERSION atomic bump + corpus archive ────────────────────────


_PY_VERSION_RE = re.compile(r"^SIMULATOR_VERSION\s*=\s*(\d+)", re.MULTILINE)
_RUST_VERSION_RE = re.compile(
    r"pub const SIMULATOR_VERSION:\s*u32\s*=\s*(\d+);"
)


def read_sim_version_py(path: Path | None = None) -> int | None:
    p = path if path is not None else VERSION_FILE_PY
    if not p.exists():
        return None
    m = _PY_VERSION_RE.search(p.read_text())
    return int(m.group(1)) if m else None


def read_sim_version_rust(path: Path | None = None) -> int | None:
    p = path if path is not None else VERSION_FILE_RUST
    if not p.exists():
        return None
    m = _RUST_VERSION_RE.search(p.read_text())
    return int(m.group(1)) if m else None


def bump_simulator_version(
    py_path: Path | None = None,
    rust_path: Path | None = None,
) -> tuple[int, int, dict[Path, str]]:
    """Atomically bump SIMULATOR_VERSION in both files (+1).

    Returns (old_version, new_version, originals_for_revert). Raises
    ValueError if the two files disagree (a half-bumped state should
    never auto-apply on top of itself — design doc §13 #25).

    Path defaults are resolved lazily so test fixtures can monkeypatch
    the module-level VERSION_FILE_* constants and have callers see the
    swap. Default-arg binding would otherwise capture the constants at
    function-definition time.
    """
    py_path = py_path if py_path is not None else VERSION_FILE_PY
    rust_path = rust_path if rust_path is not None else VERSION_FILE_RUST
    py_v = read_sim_version_py(py_path)
    rust_v = read_sim_version_rust(rust_path)
    if py_v is None or rust_v is None:
        raise ValueError(
            "could not parse SIMULATOR_VERSION from both files "
            f"(py={py_v}, rust={rust_v})"
        )
    if py_v != rust_v:
        raise ValueError(
            f"SIMULATOR_VERSION mismatch: lib.rs={rust_v}, verify.py={py_v}. "
            "Resolve the half-bumped state before applying."
        )
    new_v = py_v + 1
    originals = {
        py_path: py_path.read_text(),
        rust_path: rust_path.read_text(),
    }
    py_path.write_text(
        _PY_VERSION_RE.sub(f"SIMULATOR_VERSION = {new_v}", py_path.read_text(), count=1)
    )
    rust_path.write_text(
        _RUST_VERSION_RE.sub(
            f"pub const SIMULATOR_VERSION: u32 = {new_v};",
            rust_path.read_text(),
            count=1,
        )
    )
    return py_v, new_v, originals


def archive_failure_db(
    old_version: int,
    db_path: Path | None = None,
) -> Path | None:
    """Snapshot failure_db.jsonl to ..._snapshot_sim_v<old>.jsonl.

    Returns the snapshot path, or None if there's no failure_db to
    archive (the snapshot is a no-op in that case). Path defaults
    resolved lazily so test fixtures can monkeypatch FAILURE_DB_PATH.
    """
    p = db_path if db_path is not None else FAILURE_DB_PATH
    if not p.exists():
        return None
    snap = p.parent / f"failure_db_snapshot_sim_v{old_version}.jsonl"
    if snap.exists():
        # Don't clobber a prior archive — caller might be re-running an
        # apply on top of an in-progress one. Return the existing path
        # so revert can still find it.
        return snap
    shutil.copy2(p, snap)
    return snap


# ── Build + regression hooks ──────────────────────────────────────────────


def rebuild_rust_solver() -> tuple[bool, str]:
    """`maturin build --release` then pip install the produced wheel.

    Returns (success, combined_output). Caller should revert on False.
    """
    rust_dir = REPO_ROOT / "rust_solver"
    proc = subprocess.run(
        ["maturin", "build", "--release"],
        cwd=rust_dir, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return False, f"maturin build failed:\n{proc.stderr}\n{proc.stdout}"

    wheels_dir = rust_dir / "target" / "wheels"
    wheels = sorted(
        wheels_dir.glob("itb_solver-*.whl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not wheels:
        return False, "maturin succeeded but no wheel found in target/wheels/"
    proc = subprocess.run(
        [
            "pip3", "install", "--user", "--force-reinstall",
            "--no-deps", str(wheels[0]),
        ],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return False, f"pip install failed:\n{proc.stderr}\n{proc.stdout}"
    return True, f"built + installed {wheels[0].name}"


def run_regression() -> tuple[bool, str]:
    """`bash scripts/regression.sh`. Returns (success, output)."""
    script = REPO_ROOT / "scripts" / "regression.sh"
    if not script.exists():
        return False, f"regression script missing: {script}"
    proc = subprocess.run(
        ["bash", str(script)],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, out


# ── Markdown frontmatter mutation ──────────────────────────────────────────


def update_diagnosis_status(
    diagnosis_path: Path,
    new_status: str,
    commit_sha: str | None = None,
    extra: dict[str, str] | None = None,
) -> None:
    """Patch the YAML frontmatter in-place.

    Only the lines for ``status``, ``applied_in_commit``, and
    ``applied_at`` are touched — the body and the rest of the
    frontmatter (proposed_files, fix_snippet, etc.) survive untouched
    so re-runs / reverts can still parse them.
    """
    text = diagnosis_path.read_text()
    if not text.startswith("---"):
        return
    end = text.find("\n---", 3)
    if end < 0:
        return
    head = text[: end]
    tail = text[end:]

    head = re.sub(r"^status:\s.*$", f"status: {new_status}",
                  head, count=1, flags=re.MULTILINE)
    if commit_sha is not None:
        head = re.sub(r"^applied_in_commit:\s.*$",
                      f"applied_in_commit: {commit_sha}",
                      head, count=1, flags=re.MULTILINE)
    head = re.sub(r"^applied_at:\s.*$",
                  f"applied_at: {datetime.now(timezone.utc).isoformat()}",
                  head, count=1, flags=re.MULTILINE)
    if extra:
        for k, v in extra.items():
            head += f"\n{k}: {v}"
    diagnosis_path.write_text(head + tail)


# ── Top-level orchestrator ────────────────────────────────────────────────


def apply_diagnosis(
    failure_id: str,
    dry_run: bool = False,
    skip_regression: bool = False,
    skip_build: bool = False,
    diagnosis_path: Path | None = None,
    rebuild_fn=rebuild_rust_solver,
    regression_fn=run_regression,
) -> ApplyOutcome:
    """Walk a diagnosis through the strict apply sequence.

    ``rebuild_fn`` and ``regression_fn`` are injected so tests can
    substitute fast no-ops for the real maturin build (~25s) and
    regression (~15s). Production callers leave them at the defaults.
    """
    plan_or_err = build_apply_plan(failure_id, diagnosis_path=diagnosis_path)
    if isinstance(plan_or_err, dict):
        return ApplyOutcome(
            status="refused", plan=None, error=plan_or_err.get("error"),
            stage="plan",
        )
    plan: ApplyPlan = plan_or_err

    dirty = dirty_targets(plan)
    if dirty:
        return ApplyOutcome(
            status="refused", plan=plan,
            error=(
                "uncommitted changes in target files — refusing to clobber "
                f"user work: {dirty!r}"
            ),
            stage="git_clean",
        )

    if dry_run:
        return ApplyOutcome(status="dry_run", plan=plan)

    # Apply edits.
    try:
        edits = apply_fix(plan)
    except ValueError as e:
        return ApplyOutcome(
            status="apply_failed", plan=plan, error=str(e), stage="apply_fix"
        )
    outcome = ApplyOutcome(status="applied", plan=plan, edits=edits)

    archived = None
    if plan.needs_sim_bump:
        try:
            old, new, version_originals = bump_simulator_version()
        except ValueError as e:
            revert_fix(outcome.edits)
            return ApplyOutcome(
                status="apply_failed", plan=plan, edits={},
                error=f"simulator version bump: {e}", stage="version_bump",
            )
        # Only add files we haven't already snapshotted — apply_fix and
        # the version bump can both touch lib.rs, and we want revert to
        # restore the truly-original content (before apply_fix), not the
        # intermediate (after apply_fix, before bump).
        for path, original in version_originals.items():
            outcome.edits.setdefault(path, original)
        outcome.sim_bumped = True
        try:
            archived = archive_failure_db(old)
            outcome.archived_failure_db = archived
        except OSError as e:
            revert_fix(outcome.edits)
            return ApplyOutcome(
                status="apply_failed", plan=plan, edits={},
                error=f"failure_db archive: {e}", stage="archive_db",
            )

    if skip_build and skip_regression:
        outcome.status = "applied_unverified"
        update_diagnosis_status(plan.diagnosis_path, "applied_unverified")
        return outcome

    if not skip_build:
        ok, msg = rebuild_fn()
        if not ok:
            _full_revert(outcome)
            return ApplyOutcome(
                status="apply_failed", plan=plan, edits={},
                error=f"rebuild: {msg}", stage="rebuild",
            )

    if not skip_regression:
        ok, msg = regression_fn()
        if not ok:
            _full_revert(outcome)
            return ApplyOutcome(
                status="apply_failed", plan=plan, edits={},
                error=f"regression: {msg[-2000:]}", stage="regression",
            )

    update_diagnosis_status(plan.diagnosis_path, "applied")
    return outcome


def _full_revert(outcome: ApplyOutcome) -> None:
    """Restore every edit AND remove the failure_db archive."""
    revert_fix(outcome.edits)
    outcome.edits = {}
    if outcome.archived_failure_db and outcome.archived_failure_db.exists():
        # Only delete if it was created in *this* apply; if a prior
        # snapshot of the same version already existed, leave it alone.
        # We can't tell from here, so be conservative and leave it.
        # (The version bump revert will keep the corpus consistent.)
        pass
    outcome.sim_bumped = False
    outcome.archived_failure_db = None
