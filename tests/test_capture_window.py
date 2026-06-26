from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.capture import window


@pytest.mark.skipif(os.name == "nt", reason="macOS screenshot backend test")
def test_take_screenshot_defaults_to_quartz_without_screencapture(
    monkeypatch,
    tmp_path,
):
    calls: list[tuple[Path, dict]] = []

    def fake_quartz(output_path: Path, *, bounds: dict | None = None) -> None:
        calls.append((output_path, dict(bounds or {})))
        output_path.write_bytes(b"quartz")

    def fail_screencapture(*_args, **_kwargs) -> None:
        raise AssertionError("default screenshot path must not spawn screencapture")

    monkeypatch.delenv("ITB_SCREENSHOT_BACKEND", raising=False)
    monkeypatch.setattr(window, "_take_quartz_screenshot", fake_quartz)
    monkeypatch.setattr(window, "_run_screencapture", fail_screencapture)

    output_path = tmp_path / "screen.png"
    bounds = {"x": 12, "y": 34, "width": 640, "height": 360}

    result = window.take_screenshot(output_path, bounds=bounds)

    assert result == output_path
    assert output_path.read_bytes() == b"quartz"
    assert calls == [(output_path, bounds)]
