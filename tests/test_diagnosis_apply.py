"""PR5 — Layer 4 apply_diagnosis tests.

The apply orchestrator is the only piece in the diagnosis loop that
mutates checked-in files. These tests exercise:

  - Plan parsing: rule_match → refused with hint, agent_proposed → plan,
    Python sim targets blocked.
  - Edit apply: exact before/after replacement, ambiguous match raises,
    missing match raises.
  - Atomic SIMULATOR_VERSION bump: both files +1, mismatch refused,
    revert restores both.
  - Failure-corpus archive: snapshot path uses the *old* version; no
    clobber if a snapshot of that version already exists.
  - Orchestration: dry_run never edits, regression failure reverts every
    edit (and the version bump), success rewrites the markdown
    frontmatter to status=applied.

Maturin build + the real regression script are stubbed via injected
callbacks so tests stay fast (the real path is exercised by the
`bash scripts/regression.sh` pre-commit hook on every commit).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.solver.diagnosis_apply import (
    ApplyOutcome,
    ApplyPlan,
    apply_diagnosis,
    apply_fix,
    archive_failure_db,
    build_apply_plan,
    bump_simulator_version,
    parse_frontmatter,
    read_sim_version_py,
    read_sim_version_rust,
    revert_fix,
    update_diagnosis_status,
)


# ---------------------------------------------------------------------------
# Frontmatter parser sanity.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_parse_frontmatter_extracts_yaml_block():
    md = (
        "---\n"
        "id: x\n"
        "status: agent_proposed\n"
        "---\n"
        "## body\n"
    )
    fm, body = parse_frontmatter(md)
    assert fm["id"] == "x"
    assert fm["status"] == "agent_proposed"
    assert body.startswith("## body")


@pytest.mark.regression
def test_parse_frontmatter_returns_empty_on_legacy_markdown():
    fm, body = parse_frontmatter("plain markdown\nno frontmatter")
    assert fm == {}
    assert body.startswith("plain markdown")


# ---------------------------------------------------------------------------
# Plan construction.
# ---------------------------------------------------------------------------


def _write_diag(tmp_path: Path, frontmatter_lines: list[str], body: str = "") -> Path:
    md = "---\n" + "\n".join(frontmatter_lines) + "\n---\n" + body
    p = tmp_path / "diag.md"
    p.write_text(md)
    return p


@pytest.mark.regression
def test_build_apply_plan_refuses_rule_match(tmp_path):
    md = _write_diag(tmp_path, [
        "id: x", "status: rule_match", "target_language: rust",
    ])
    res = build_apply_plan("x", diagnosis_path=md)
    assert isinstance(res, dict)
    assert res["status"] == "ERROR"
    assert "rule_match" in res["error"]


@pytest.mark.regression
def test_build_apply_plan_refuses_python_sim_target(tmp_path):
    md = _write_diag(tmp_path, [
        "id: x", "status: agent_proposed", "target_language: rust",
        "proposed_files:",
        "  - path: src/solver/simulate.py",
        "    lines: [10]",
        "fix_snippet:",
        "  before: |",
        "    a",
        "  after: |",
        "    b",
    ])
    res = build_apply_plan("x", diagnosis_path=md)
    assert isinstance(res, dict)
    assert "Python sim is" in res["error"]


@pytest.mark.regression
def test_build_apply_plan_returns_plan_for_well_formed_agent_proposed(tmp_path):
    """Use rust_solver/src/lib.rs as a real, resolvable target so the
    path-existence check passes in the repo."""
    md = _write_diag(tmp_path, [
        "id: x", "status: agent_proposed", "target_language: rust",
        "confidence: medium",
        "proposed_files:",
        "  - path: rust_solver/src/lib.rs",
        "    lines: [1]",
        "fix_snippet:",
        "  before: |",
        "    use pyo3::prelude::*;",
        "  after: |",
        "    use pyo3::prelude::*;  // touched",
    ])
    plan = build_apply_plan("x", diagnosis_path=md)
    assert isinstance(plan, ApplyPlan)
    assert plan.status == "agent_proposed"
    assert plan.needs_sim_bump is True
    assert plan.confidence == "medium"


# ---------------------------------------------------------------------------
# Edit apply / revert against a sandbox file.
# ---------------------------------------------------------------------------


@pytest.fixture
def sandbox_target(tmp_path, monkeypatch):
    """A fake `rust_solver/src/lib.rs`-shaped file inside tmp_path.

    Monkeypatches diagnosis_apply.REPO_ROOT to point at tmp_path so
    apply_fix resolves the agent's relative paths against the sandbox
    instead of the real repo. Tests never touch the real source tree.
    """
    fake_root = tmp_path / "fake_repo"
    (fake_root / "rust_solver" / "src").mkdir(parents=True)
    target = fake_root / "rust_solver" / "src" / "lib.rs"
    target.write_text(
        "fn alpha() {\n"
        "    println!(\"alpha\");\n"
        "}\n"
        "\n"
        "fn beta() {\n"
        "    println!(\"beta\");\n"
        "}\n"
    )
    monkeypatch.setattr("src.solver.diagnosis_apply.REPO_ROOT", fake_root)
    return fake_root, target


@pytest.mark.regression
def test_apply_fix_replaces_unique_block(sandbox_target):
    fake_root, target = sandbox_target
    plan = ApplyPlan(
        failure_id="x",
        diagnosis_path=fake_root / "diag.md",
        status="agent_proposed",
        confidence="high",
        target_language="rust",
        suspect_files=[{"path": "rust_solver/src/lib.rs", "lines": [2]}],
        fix_snippet={
            "before": "    println!(\"alpha\");",
            "after": "    println!(\"alpha — patched\");",
        },
    )
    originals = apply_fix(plan)
    assert target in originals
    assert "alpha — patched" in target.read_text()
    assert "println!(\"beta\")" in target.read_text(), "untouched code preserved"


@pytest.mark.regression
def test_apply_fix_raises_on_ambiguous_match(sandbox_target):
    fake_root, target = sandbox_target
    target.write_text("X\nX\n")  # 2 occurrences
    plan = ApplyPlan(
        failure_id="x",
        diagnosis_path=fake_root / "diag.md",
        status="agent_proposed",
        confidence="high",
        target_language="rust",
        suspect_files=[{"path": "rust_solver/src/lib.rs", "lines": [1]}],
        fix_snippet={"before": "X", "after": "Y"},
    )
    with pytest.raises(ValueError, match="appears 2 times"):
        apply_fix(plan)


@pytest.mark.regression
def test_apply_fix_raises_on_no_match(sandbox_target):
    fake_root, target = sandbox_target
    plan = ApplyPlan(
        failure_id="x",
        diagnosis_path=fake_root / "diag.md",
        status="agent_proposed",
        confidence="high",
        target_language="rust",
        suspect_files=[{"path": "rust_solver/src/lib.rs", "lines": [1]}],
        fix_snippet={"before": "NEVER_PRESENT", "after": "X"},
    )
    with pytest.raises(ValueError, match="not found"):
        apply_fix(plan)


@pytest.mark.regression
def test_revert_restores_original(sandbox_target):
    fake_root, target = sandbox_target
    original_text = target.read_text()
    plan = ApplyPlan(
        failure_id="x",
        diagnosis_path=fake_root / "diag.md",
        status="agent_proposed",
        confidence="high",
        target_language="rust",
        suspect_files=[{"path": "rust_solver/src/lib.rs", "lines": [2]}],
        fix_snippet={
            "before": "println!(\"alpha\");",
            "after": "println!(\"DOOM\");",
        },
    )
    originals = apply_fix(plan)
    assert "DOOM" in target.read_text()
    revert_fix(originals)
    assert target.read_text() == original_text


# ---------------------------------------------------------------------------
# SIMULATOR_VERSION atomic bump.
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_version_files(tmp_path):
    rust = tmp_path / "lib.rs"
    py = tmp_path / "verify.py"
    rust.write_text(
        "// some preamble\n"
        "pub const SIMULATOR_VERSION: u32 = 10;\n"
        "// trailing\n"
    )
    py.write_text(
        "# header\n"
        "SIMULATOR_VERSION = 10\n"
        "# footer\n"
    )
    return py, rust


@pytest.mark.regression
def test_bump_simulator_version_is_atomic(fake_version_files):
    py, rust = fake_version_files
    old, new, originals = bump_simulator_version(py_path=py, rust_path=rust)
    assert old == 10
    assert new == 11
    assert "SIMULATOR_VERSION = 11" in py.read_text()
    assert "pub const SIMULATOR_VERSION: u32 = 11;" in rust.read_text()
    # Surrounding text untouched.
    assert "# header" in py.read_text()
    assert "// some preamble" in rust.read_text()
    assert py in originals and rust in originals


@pytest.mark.regression
def test_bump_simulator_version_refuses_mismatch(fake_version_files):
    py, rust = fake_version_files
    py.write_text(py.read_text().replace("= 10", "= 9"))
    with pytest.raises(ValueError, match="mismatch"):
        bump_simulator_version(py_path=py, rust_path=rust)


@pytest.mark.regression
def test_bump_can_be_reverted_via_originals(fake_version_files):
    py, rust = fake_version_files
    py_text_before = py.read_text()
    rust_text_before = rust.read_text()
    _, _, originals = bump_simulator_version(py_path=py, rust_path=rust)
    revert_fix(originals)
    assert py.read_text() == py_text_before
    assert rust.read_text() == rust_text_before


# ---------------------------------------------------------------------------
# failure_db archive.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_archive_failure_db_creates_snapshot(tmp_path):
    db = tmp_path / "failure_db.jsonl"
    db.write_text('{"id": "row1"}\n')
    snap = archive_failure_db(old_version=10, db_path=db)
    assert snap is not None
    assert snap.name == "failure_db_snapshot_sim_v10.jsonl"
    assert snap.read_text() == '{"id": "row1"}\n'


@pytest.mark.regression
def test_archive_failure_db_does_not_clobber_existing(tmp_path):
    db = tmp_path / "failure_db.jsonl"
    db.write_text("new\n")
    pre = tmp_path / "failure_db_snapshot_sim_v10.jsonl"
    pre.write_text("old\n")
    snap = archive_failure_db(old_version=10, db_path=db)
    assert snap == pre
    assert pre.read_text() == "old\n"  # untouched


@pytest.mark.regression
def test_archive_failure_db_returns_none_when_no_db(tmp_path):
    assert archive_failure_db(old_version=10, db_path=tmp_path / "missing.jsonl") is None


# ---------------------------------------------------------------------------
# update_diagnosis_status patches frontmatter in place.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_update_diagnosis_status_rewrites_only_frontmatter(tmp_path):
    md = tmp_path / "d.md"
    md.write_text(
        "---\n"
        "id: x\n"
        "status: agent_proposed\n"
        "applied_in_commit: null\n"
        "applied_at: null\n"
        "---\n"
        "## body\nuntouched\n"
    )
    update_diagnosis_status(md, "applied", commit_sha="abc123")
    text = md.read_text()
    assert "status: applied" in text
    assert "applied_in_commit: abc123" in text
    assert "## body" in text and "untouched" in text


# ---------------------------------------------------------------------------
# Top-level orchestrator.
# ---------------------------------------------------------------------------


def _stub_rebuild_ok():
    return True, "stub: rebuild succeeded"


def _stub_rebuild_fail():
    return False, "stub: rebuild failed"


def _stub_regression_ok():
    return True, "stub: regression passed"


def _stub_regression_fail():
    return False, "stub: regression failed"


def _setup_sandbox_with_diagnosis(tmp_path, monkeypatch, sim_bump=True):
    """Build a self-contained sandbox: fake repo root, version files,
    a target file, a diagnosis markdown that fixes a unique snippet."""
    fake_root = tmp_path / "fake_repo"
    rs_dir = fake_root / "rust_solver" / "src"
    py_dir = fake_root / "src" / "solver"
    rec_dir = fake_root / "recordings"
    diag_dir = rec_dir / "test_run" / "diagnoses"
    rs_dir.mkdir(parents=True)
    py_dir.mkdir(parents=True)
    diag_dir.mkdir(parents=True)

    target = rs_dir / "lib.rs"
    target.write_text(
        "// preamble\n"
        "fn unique_marker_for_apply() {\n"
        "    let x = 1;\n"
        "}\n"
        "\n"
        "pub const SIMULATOR_VERSION: u32 = 10;\n"
    )
    py_ver = py_dir / "verify.py"
    py_ver.write_text(
        "# verify shim\n"
        "SIMULATOR_VERSION = 10\n"
    )
    failure_db = rec_dir / "failure_db.jsonl"
    failure_db.write_text('{"id": "test_failure"}\n')

    # Choose target file based on whether we want a sim bump.
    if sim_bump:
        suspect_path = "rust_solver/src/lib.rs"
        before = "    let x = 1;"
        after = "    let x = 2;  // patched"
    else:
        # A non-sim file — but we don't have one in the sandbox; create one.
        readme = fake_root / "scripts" / "helper.sh"
        readme.parent.mkdir(parents=True)
        readme.write_text("#!/bin/bash\necho hi\n")
        suspect_path = "scripts/helper.sh"
        before = "echo hi"
        after = "echo bye"

    diag_path = diag_dir / "test_failure.md"
    diag_path.write_text(
        "---\n"
        "id: test_failure\n"
        "failure_id: test_failure\n"
        "run_id: test_run\n"
        "mission: 0\n"
        "turn: 1\n"
        "action_index: 0\n"
        "sim_version_at_diagnosis: 10\n"
        "status: agent_proposed\n"
        "confidence: medium\n"
        "applied_in_commit: null\n"
        "applied_at: null\n"
        "target_language: rust\n"
        f"proposed_files:\n  - path: {suspect_path}\n    lines: [3]\n"
        "rules_matched: []\n"
        "agent_invoked: true\n"
        "fix_snippet:\n"
        f"  before: |\n    {before}\n"
        f"  after: |\n    {after}\n"
        "---\n"
        "## body\n"
    )

    monkeypatch.setattr("src.solver.diagnosis_apply.REPO_ROOT", fake_root)
    monkeypatch.setattr("src.solver.diagnosis_apply.RECORDINGS_DIR", rec_dir)
    monkeypatch.setattr("src.solver.diagnosis_apply.VERSION_FILE_RUST", target)
    monkeypatch.setattr("src.solver.diagnosis_apply.VERSION_FILE_PY", py_ver)
    monkeypatch.setattr("src.solver.diagnosis_apply.FAILURE_DB_PATH", failure_db)
    # Defang dirty-targets check; tests don't init a git repo in the sandbox.
    monkeypatch.setattr("src.solver.diagnosis_apply.dirty_targets", lambda plan: [])

    return {
        "fake_root": fake_root,
        "target": target,
        "py_ver": py_ver,
        "failure_db": failure_db,
        "diag_path": diag_path,
    }


@pytest.mark.regression
def test_apply_dry_run_makes_no_edits(tmp_path, monkeypatch):
    sb = _setup_sandbox_with_diagnosis(tmp_path, monkeypatch)
    target_text_before = sb["target"].read_text()
    py_text_before = sb["py_ver"].read_text()

    outcome = apply_diagnosis(
        "test_failure", dry_run=True, diagnosis_path=sb["diag_path"],
    )
    assert outcome.status == "dry_run"
    assert outcome.plan is not None
    assert outcome.plan.needs_sim_bump is True
    # Files untouched.
    assert sb["target"].read_text() == target_text_before
    assert sb["py_ver"].read_text() == py_text_before


@pytest.mark.regression
def test_apply_full_path_writes_files_and_bumps_version(tmp_path, monkeypatch):
    sb = _setup_sandbox_with_diagnosis(tmp_path, monkeypatch)

    outcome = apply_diagnosis(
        "test_failure",
        diagnosis_path=sb["diag_path"],
        rebuild_fn=_stub_rebuild_ok,
        regression_fn=_stub_regression_ok,
    )
    assert outcome.status == "applied", outcome.error
    assert "let x = 2;" in sb["target"].read_text()
    assert "SIMULATOR_VERSION = 11" in sb["py_ver"].read_text()
    assert "pub const SIMULATOR_VERSION: u32 = 11;" in sb["target"].read_text()
    # Archive landed.
    snap = sb["failure_db"].parent / "failure_db_snapshot_sim_v10.jsonl"
    assert snap.exists()
    # Frontmatter rewritten.
    diag_text = sb["diag_path"].read_text()
    assert "status: applied" in diag_text


@pytest.mark.regression
def test_apply_reverts_everything_on_regression_failure(tmp_path, monkeypatch):
    sb = _setup_sandbox_with_diagnosis(tmp_path, monkeypatch)
    target_text_before = sb["target"].read_text()
    py_text_before = sb["py_ver"].read_text()

    outcome = apply_diagnosis(
        "test_failure",
        diagnosis_path=sb["diag_path"],
        rebuild_fn=_stub_rebuild_ok,
        regression_fn=_stub_regression_fail,
    )
    assert outcome.status == "apply_failed"
    assert outcome.stage == "regression"
    # Source + version files restored.
    assert sb["target"].read_text() == target_text_before
    assert sb["py_ver"].read_text() == py_text_before
    # Markdown unchanged (still agent_proposed).
    assert "status: agent_proposed" in sb["diag_path"].read_text()


@pytest.mark.regression
def test_apply_reverts_on_rebuild_failure(tmp_path, monkeypatch):
    sb = _setup_sandbox_with_diagnosis(tmp_path, monkeypatch)
    target_text_before = sb["target"].read_text()

    outcome = apply_diagnosis(
        "test_failure",
        diagnosis_path=sb["diag_path"],
        rebuild_fn=_stub_rebuild_fail,
        regression_fn=_stub_regression_ok,  # never reached
    )
    assert outcome.status == "apply_failed"
    assert outcome.stage == "rebuild"
    assert sb["target"].read_text() == target_text_before


@pytest.mark.regression
def test_dirty_targets_preserves_leading_space_in_path(monkeypatch):
    """`git status --porcelain` formats worktree-only changes as ` M PATH`
    (leading space for the X status). A naive proc.stdout.strip() eats
    that space and shifts every byte left, lopping the first character
    off the path — surfaced as 'ust_solver/src/lib.rs' on a live run.
    Regression: the slicer must keep the path intact."""
    from src.solver import diagnosis_apply

    class _FakeProc:
        returncode = 0
        # Two lines, both worktree-only modifications. The first path
        # has its leading-space-stripping bug; the second one stays
        # correct either way (so the test isolates the bug).
        stdout = " M rust_solver/src/lib.rs\n M src/solver/verify.py\n"

    def _fake_run(*a, **k):
        return _FakeProc()

    monkeypatch.setattr(diagnosis_apply.subprocess, "run", _fake_run)

    plan = diagnosis_apply.ApplyPlan(
        failure_id="x",
        diagnosis_path=Path("ignored"),
        status="agent_proposed",
        confidence="high",
        target_language="rust",
        suspect_files=[
            {"path": "rust_solver/src/lib.rs", "lines": [1]},
        ],
        needs_sim_bump=True,
    )
    dirty = diagnosis_apply.dirty_targets(plan)
    assert "rust_solver/src/lib.rs" in dirty, (
        f"expected full path; got {dirty!r} — leading-space-strip bug regressed"
    )
    assert "src/solver/verify.py" in dirty


@pytest.mark.regression
def test_apply_skip_build_skip_regression_marks_applied_unverified(
    tmp_path, monkeypatch
):
    sb = _setup_sandbox_with_diagnosis(tmp_path, monkeypatch)
    outcome = apply_diagnosis(
        "test_failure",
        diagnosis_path=sb["diag_path"],
        skip_build=True, skip_regression=True,
    )
    assert outcome.status == "applied_unverified"
    diag_text = sb["diag_path"].read_text()
    assert "status: applied_unverified" in diag_text
