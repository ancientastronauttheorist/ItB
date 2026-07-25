"""Tests for deterministic immutable Observatory controller artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.itb_trace import main as trace_cli
from src.observatory.controller_bundle import (
    ControllerBundleError,
    build_controller_bundle,
    controller_bundle_sha256,
    render_controller_bundle,
)
from src.observatory.trace_store import stable_file_sha256


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "src" / "bridge" / "observatory_trace.lua"
CONTROLLER_PATH = ROOT / "src" / "bridge" / "observatory_controller.lua"


def test_bundle_is_deterministic_and_covers_both_exact_sources():
    runtime = RUNTIME_PATH.read_bytes().decode("utf-8")
    controller = CONTROLLER_PATH.read_bytes().decode("utf-8")
    first = render_controller_bundle(runtime, controller)
    second = build_controller_bundle(
        runtime_path=RUNTIME_PATH,
        controller_path=CONTROLLER_PATH,
    )

    assert first == second
    assert controller_bundle_sha256(first) == hashlib.sha256(
        first.encode("utf-8")
    ).hexdigest()
    assert controller_bundle_sha256(
        render_controller_bundle(runtime + "\n-- changed", controller)
    ) != controller_bundle_sha256(first)
    assert controller_bundle_sha256(
        render_controller_bundle(runtime, controller + "\n-- changed")
    ) != controller_bundle_sha256(first)


def test_bundle_uses_noncolliding_lua_long_brackets():
    rendered = render_controller_bundle(
        "local marker = ]=]\nreturn {new = function() end}",
        "return {bind_runtime = function(value) return value end}",
    )
    assert "[==[" in rendered
    assert "] == nil" not in rendered


@pytest.mark.parametrize("runtime,controller", [("", "ok"), ("ok", "")])
def test_bundle_rejects_empty_sources(runtime, controller):
    with pytest.raises(ControllerBundleError, match="non-empty"):
        render_controller_bundle(runtime, controller)


def test_build_controller_cli_publishes_content_addressed_read_only_file(
    tmp_path,
    capsys,
):
    output = tmp_path / "controllers"
    assert trace_cli(
        [
            "build-controller",
            "--runtime-source",
            str(RUNTIME_PATH),
            "--controller-source",
            str(CONTROLLER_PATH),
            "--output-root",
            str(output),
        ]
    ) == 0
    line = capsys.readouterr().out.strip()
    path = next(output.glob("itb_observatory_controller_*.lua"))
    digest = stable_file_sha256(path)
    assert path.name == f"itb_observatory_controller_{digest}.lua"
    assert f"sha256={digest}" in line
    assert path.stat().st_mode & 0o222 == 0
    assert trace_cli(
        [
            "build-controller",
            "--runtime-source",
            str(RUNTIME_PATH),
            "--controller-source",
            str(CONTROLLER_PATH),
            "--output-root",
            str(output),
        ]
    ) == 2
    assert "already exists" in capsys.readouterr().err
