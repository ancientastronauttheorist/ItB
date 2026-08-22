from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import itb_observatory_native_rng_turn as cli


def test_control_turn_writes_create_only_valid_receipt(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("ITB_ARTIFACT_ROOT", str(runtime))
    monkeypatch.setenv("ITB_SESSION_FILE", str(runtime / "session.json"))
    monkeypatch.setattr(
        cli,
        "cmd_auto_turn",
        lambda **kwargs: {
            "status": "ok",
            "turn": 1,
            "actions_completed": 3,
            "desyncs_detected": 0,
            "post_phase": "combat_player",
        },
    )
    monkeypatch.setattr(
        cli.NativeRngTurnBoundary,
        "abort",
        lambda self: setattr(self, "state", "complete") or self.summary(),
    )
    output = tmp_path / "control.json"

    code = cli.main(
        [
            "--pair-id",
            "pair-001",
            "--condition",
            "control",
            "--capture-id",
            "native-rng-pair-001-control",
            "--trial-output",
            str(output),
        ]
    )

    assert code == 0
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["valid_trial"] is True
    assert receipt["condition"] == "control"


def test_exact_turn_requires_all_build_keyed_inputs(tmp_path):
    code = cli.main(
        [
            "--pair-id",
            "pair-001",
            "--condition",
            "exact_hook",
            "--capture-id",
            "native-rng-pair-001-exact",
            "--trial-output",
            str(tmp_path / "exact.json"),
        ]
    )

    assert code == 2
    assert not (tmp_path / "exact.json").exists()


def test_spawn_span_requires_outcome_and_span_outputs(tmp_path):
    code = cli.main(
        [
            "--pair-id",
            "pair-001",
            "--condition",
            "spawn_span",
            "--capture-id",
            "native-rng-pair-001-span",
            "--trial-output",
            str(tmp_path / "span.json"),
        ]
    )

    assert code == 2
    assert not (tmp_path / "span.json").exists()


def test_trial_output_is_never_overwritten(tmp_path, monkeypatch):
    # Validation stops before any session touching work.
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("ITB_ARTIFACT_ROOT", str(runtime))
    monkeypatch.setenv("ITB_SESSION_FILE", str(runtime / "session.json"))
    output = tmp_path / "exists.json"
    output.write_text("owner", encoding="utf-8")

    code = cli.main(
        [
            "--pair-id",
            "pair-001",
            "--condition",
            "control",
            "--capture-id",
            "native-rng-pair-001-control",
            "--trial-output",
            str(output),
        ]
    )

    assert code == 2
    assert output.read_text(encoding="utf-8") == "owner"


def test_main_forces_utf8_before_parsing(monkeypatch):
    calls = []

    class _Stream:
        def reconfigure(self, **kwargs):
            calls.append(kwargs)

        def write(self, value):
            return len(value)

        def flush(self):
            return None

    monkeypatch.setattr(cli.sys, "stdout", _Stream())
    monkeypatch.setattr(cli.sys, "stderr", _Stream())

    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert calls == [
        {"encoding": "utf-8", "errors": "replace"},
        {"encoding": "utf-8", "errors": "replace"},
    ]
