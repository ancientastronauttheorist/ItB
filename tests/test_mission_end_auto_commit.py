"""mission_end auto-commit helper tests.

The real ``_mission_end_auto_commit`` shells out to ``git`` for add /
commit / push. These tests swap ``subprocess.run`` for a fake so we
can assert the command sequence, the outcome classification, and
the opt-out path without touching the repo or the network.

``_mission_end_auto_commit`` accepts a ``repo_root`` kwarg for
testability — tests point it at a tmp directory and place synthetic
artifacts there so the existence checks fire naturally.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from src.loop import commands as loop_commands
from src.loop.session import RunSession


RUN_ID = "20260420_000000_test"


def _session() -> RunSession:
    return RunSession(
        run_id=RUN_ID,
        current_mission="Test Archipelago",
        mission_index=0,
    )


def _plant_artifacts(repo: Path) -> None:
    """Create the candidate files the helper looks for."""
    (repo / "recordings" / RUN_ID).mkdir(parents=True, exist_ok=True)
    (repo / "recordings" / RUN_ID / "m00_outcome.json").write_text("{}")
    (repo / "sessions").mkdir(parents=True, exist_ok=True)
    (repo / "sessions" / "active_session.json").write_text("{}")


class _FakeCompleted:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _SubprocessDouble:
    """Record git calls and serve canned responses keyed by git subcommand."""

    def __init__(self, responses: dict[str, _FakeCompleted] | None = None):
        self.calls: list[list[str]] = []
        self.responses = responses or {}

    def run(self, cmd: list[str], *args, **kwargs):
        self.calls.append(cmd)
        # Each call shape: ["git", "-C", "<repo>", "<subcmd>", ...]
        key = cmd[3] if len(cmd) > 3 else ""
        resp = self.responses.get(key, _FakeCompleted(0, "", ""))
        if kwargs.get("check") and resp.returncode != 0:
            raise subprocess.CalledProcessError(
                resp.returncode, cmd, output=resp.stdout, stderr=resp.stderr,
            )
        return resp


# ── happy path ───────────────────────────────────────────────────────────────


def test_auto_commit_happy_path(monkeypatch, tmp_path):
    _plant_artifacts(tmp_path)
    double = _SubprocessDouble(responses={
        "add": _FakeCompleted(0),
        "diff": _FakeCompleted(1),      # 1 = staged changes present
        "commit": _FakeCompleted(0),
        "rev-parse": _FakeCompleted(0, stdout="abc1234\n"),
        "push": _FakeCompleted(0),
    })
    monkeypatch.setattr("subprocess.run", double.run)

    out = loop_commands._mission_end_auto_commit(
        _session(), "win", 0, repo_root=tmp_path,
    )

    add_cmd = next(c for c in double.calls if c[3] == "add")
    assert f"recordings/{RUN_ID}" in add_cmd
    assert "sessions/active_session.json" in add_cmd
    # logs + weapon_overrides_staged weren't planted; they must NOT appear.
    assert not any("logs/" in a for a in add_cmd)
    assert not any("weapon_overrides_staged" in a for a in add_cmd)

    assert out["status"] == "committed"
    assert out["commit"] == "abc1234"
    assert out["pushed"] is True


# ── skip paths ───────────────────────────────────────────────────────────────


def test_auto_commit_skips_when_no_artifacts(tmp_path):
    # No artifacts planted — helper must bail before touching git.
    out = loop_commands._mission_end_auto_commit(
        _session(), "win", 0, repo_root=tmp_path,
    )
    assert out["status"] == "skipped"
    assert "no stageable" in out["reason"]


def test_auto_commit_skips_when_no_changes(monkeypatch, tmp_path):
    _plant_artifacts(tmp_path)
    double = _SubprocessDouble(responses={
        "add": _FakeCompleted(0),
        "diff": _FakeCompleted(0),      # 0 = nothing staged
    })
    monkeypatch.setattr("subprocess.run", double.run)

    out = loop_commands._mission_end_auto_commit(
        _session(), "win", 0, repo_root=tmp_path,
    )
    assert out["status"] == "skipped"
    assert "no changes" in out["reason"]
    # Commit must not have been attempted.
    assert not any(c[3] == "commit" for c in double.calls if len(c) > 3)


# ── failure paths ────────────────────────────────────────────────────────────


def test_auto_commit_reports_add_failure(monkeypatch, tmp_path):
    _plant_artifacts(tmp_path)
    double = _SubprocessDouble(responses={
        "add": _FakeCompleted(128, stderr="fatal: pathspec did not match"),
    })
    monkeypatch.setattr("subprocess.run", double.run)

    out = loop_commands._mission_end_auto_commit(
        _session(), "win", 0, repo_root=tmp_path,
    )
    assert out["status"] == "failed"
    assert out["stage"] == "add"
    assert "pathspec" in out["error"]


def test_auto_commit_commit_ok_push_fails(monkeypatch, tmp_path):
    _plant_artifacts(tmp_path)
    double = _SubprocessDouble(responses={
        "add": _FakeCompleted(0),
        "diff": _FakeCompleted(1),
        "commit": _FakeCompleted(0),
        "rev-parse": _FakeCompleted(0, stdout="deadbee\n"),
        "push": _FakeCompleted(1, stderr="fatal: unable to access origin"),
    })
    monkeypatch.setattr("subprocess.run", double.run)

    out = loop_commands._mission_end_auto_commit(
        _session(), "loss", 3, repo_root=tmp_path,
    )
    assert out["status"] == "committed"
    assert out["commit"] == "deadbee"
    assert out["pushed"] is False
    assert "unable to access" in out["push_error"]


def test_auto_commit_includes_co_author_line(monkeypatch, tmp_path):
    _plant_artifacts(tmp_path)
    double = _SubprocessDouble(responses={
        "add": _FakeCompleted(0),
        "diff": _FakeCompleted(1),
        "commit": _FakeCompleted(0),
        "rev-parse": _FakeCompleted(0, stdout="feedf00\n"),
        "push": _FakeCompleted(0),
    })
    monkeypatch.setattr("subprocess.run", double.run)

    loop_commands._mission_end_auto_commit(
        _session(), "win", 0, repo_root=tmp_path,
    )
    commit_cmd = next(c for c in double.calls if c[3] == "commit")
    # commit_cmd shape: ["git", "-C", repo, "commit", "-m", "<msg>"]
    msg = commit_cmd[-1]
    assert "Co-Authored-By: Claude" in msg
    assert "Mission end: Test Archipelago — win" in msg
    assert f"({RUN_ID} m00)" in msg


# ── opt-out flag path ────────────────────────────────────────────────────────


def test_cmd_mission_end_no_commit_skips_helper(monkeypatch, tmp_path):
    # Redirect the outcome-writer sinks so cmd_mission_end doesn't touch disk.
    s = _session()
    monkeypatch.setattr(RunSession, "load", classmethod(lambda cls: s))
    monkeypatch.setattr(loop_commands, "_recording_dir", lambda sess: tmp_path)
    monkeypatch.setattr(loop_commands, "_atomic_json_write", lambda p, d: None)
    monkeypatch.setattr(loop_commands, "_write_manifest", lambda sess, d: None)

    called: list = []
    monkeypatch.setattr(
        loop_commands, "_mission_end_auto_commit",
        lambda *a, **kw: called.append((a, kw)) or {"should": "not_run"},
    )

    out = loop_commands.cmd_mission_end("win", no_commit=True)
    assert "git" not in out
    assert called == []


def test_cmd_mission_end_default_invokes_helper(monkeypatch, tmp_path):
    s = _session()
    monkeypatch.setattr(RunSession, "load", classmethod(lambda cls: s))
    monkeypatch.setattr(loop_commands, "_recording_dir", lambda sess: tmp_path)
    monkeypatch.setattr(loop_commands, "_atomic_json_write", lambda p, d: None)
    monkeypatch.setattr(loop_commands, "_write_manifest", lambda sess, d: None)

    called: list = []
    monkeypatch.setattr(
        loop_commands, "_mission_end_auto_commit",
        lambda sess, outcome, mi: called.append((sess.run_id, outcome, mi))
        or {"status": "committed", "commit": "abc", "pushed": True},
    )

    out = loop_commands.cmd_mission_end("win")
    assert len(called) == 1
    assert called[0] == (RUN_ID, "win", 0)
    assert out["git"]["status"] == "committed"
