from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.observatory.campaign_cleanup import CampaignCleanupError, cleanup_campaign


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, bytes]:
    install = tmp_path / "game"
    scripts = install / "scripts"
    bridge = tmp_path / "bridge"
    baseline = tmp_path / "staging" / "modloader.lua"
    scripts.mkdir(parents=True)
    bridge.mkdir()
    baseline.parent.mkdir()
    (install / "Breach.exe").write_bytes(b"pinned elsewhere")
    (scripts / "modloader.lua").write_bytes(b"instrumented")
    (scripts / "itb_observatory_helper.dll").write_bytes(b"helper")
    (scripts / "observatory_trace.lua").write_bytes(b"trace")
    (scripts / "ordinary.lua").write_bytes(b"keep")
    (bridge / "itb_observatory_result.json").write_bytes(b"result")
    (bridge / "state.json").write_bytes(b"keep")
    baseline_bytes = b"baseline loader\n"
    baseline.write_bytes(baseline_bytes)
    return install, bridge, baseline, baseline_bytes


def test_cleanup_is_a_dry_run_without_explicit_authorization(tmp_path: Path):
    install, bridge, baseline, baseline_bytes = _fixture(tmp_path)
    report = cleanup_campaign(
        install_dir=install,
        bridge_dir=bridge,
        baseline_modloader=baseline,
        expected_baseline_sha256=_sha256(baseline_bytes),
    )

    assert report["applied"] is False
    assert report["install_removed_file_count"] == 2
    assert report["bridge_removed_file_count"] == 1
    assert (install / "scripts" / "itb_observatory_helper.dll").exists()
    assert (install / "scripts" / "modloader.lua").read_bytes() == b"instrumented"


def test_cleanup_restores_loader_and_removes_only_experimental_files(tmp_path: Path):
    install, bridge, baseline, baseline_bytes = _fixture(tmp_path)
    report = cleanup_campaign(
        install_dir=install,
        bridge_dir=bridge,
        baseline_modloader=baseline,
        expected_baseline_sha256=_sha256(baseline_bytes),
        allow_cleanup=True,
    )

    assert report["applied"] is True
    assert report["remaining_install_experimental_file_count"] == 0
    assert report["remaining_bridge_experimental_file_count"] == 0
    assert (install / "scripts" / "modloader.lua").read_bytes() == baseline_bytes
    assert (install / "scripts" / "ordinary.lua").read_bytes() == b"keep"
    assert (bridge / "state.json").read_bytes() == b"keep"


def test_cleanup_rejects_an_unpinned_baseline(tmp_path: Path):
    install, bridge, baseline, _ = _fixture(tmp_path)
    with pytest.raises(CampaignCleanupError, match="baseline modloader hash mismatch"):
        cleanup_campaign(
            install_dir=install,
            bridge_dir=bridge,
            baseline_modloader=baseline,
            expected_baseline_sha256="0" * 64,
            allow_cleanup=True,
        )

    assert (install / "scripts" / "itb_observatory_helper.dll").exists()


def test_cleanup_rejects_a_baseline_inside_an_active_root(tmp_path: Path):
    install, bridge, _, baseline_bytes = _fixture(tmp_path)
    active_baseline = install / "scripts" / "baseline.lua"
    active_baseline.write_bytes(baseline_bytes)

    with pytest.raises(CampaignCleanupError, match="outside active roots"):
        cleanup_campaign(
            install_dir=install,
            bridge_dir=bridge,
            baseline_modloader=active_baseline,
            expected_baseline_sha256=_sha256(baseline_bytes),
            allow_cleanup=True,
        )
