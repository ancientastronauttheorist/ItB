from __future__ import annotations

import pytest

from scripts import itb_observatory_spawn_coordinate_rng_trial as cli


def _required_args(tmp_path):
    return [
        "--pair-id",
        "pair001",
        "--capture-id",
        "combined-pair001",
        "--rng-build-receipt",
        str(tmp_path / "rng-receipt.json"),
        "--rng-module",
        str(tmp_path / "rng.dll"),
        "--rng-return-map",
        str(tmp_path / "return-map.json"),
        "--rng-restore-hashes",
        str(tmp_path / "restore.json"),
        "--coordinate-build-receipt",
        str(tmp_path / "coordinate-receipt.json"),
        "--coordinate-module",
        str(tmp_path / "coordinate.dll"),
        "--trial-output",
        str(tmp_path / "trial.json"),
        "--outcome-output",
        str(tmp_path / "outcome.json"),
        "--rng-checkpoint-output",
        str(tmp_path / "checkpoint.json"),
        "--coordinate-snapshot-output",
        str(tmp_path / "coordinate.json"),
        "--coordinate-analysis-output",
        str(tmp_path / "coordinate-analysis.json"),
        "--attribution-output",
        str(tmp_path / "attribution.json"),
    ]


def test_runtime_root_is_required_before_any_session_work(tmp_path, monkeypatch):
    monkeypatch.delenv("ITB_ARTIFACT_ROOT", raising=False)
    monkeypatch.delenv("ITB_SESSION_FILE", raising=False)

    assert cli.main(_required_args(tmp_path)) == 2
    assert not (tmp_path / "trial.json").exists()


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
