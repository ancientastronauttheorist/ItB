from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_itb_observatory_spawn_span_controller as builder


ROOT = Path(__file__).resolve().parents[1]
MODLOADER = ROOT / "src" / "bridge" / "modloader.lua"


def test_build_is_content_addressed_and_reproducible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    spawner = tmp_path / "scripts" / "spawner_backend.lua"
    spawner.parent.mkdir()
    # The builder intentionally pins the exact installed bytes.  Patch only the
    # digest constant in this isolated test so the packaging logic remains real.
    spawner.write_bytes(b"exact pinned spawner\n")
    spawner_payload = spawner.read_bytes()
    real_sha256 = builder._sha256
    monkeypatch.setattr(
        builder,
        "_sha256",
        lambda payload: (
            builder.SPAWNER_SHA256
            if payload == spawner_payload
            else real_sha256(payload)
        ),
    )
    first = builder.build(
        spawner_source=spawner,
        modloader=MODLOADER,
        output_root=tmp_path / "first",
    )
    second = builder.build(
        spawner_source=spawner,
        modloader=MODLOADER,
        output_root=tmp_path / "second",
    )
    first_module = Path(first["module"])
    second_module = Path(second["module"])
    assert first_module.read_bytes() == second_module.read_bytes()
    assert first["controller_sha256"] == second["controller_sha256"]
    receipt = json.loads(Path(first["receipt"]).read_text(encoding="utf-8"))
    assert receipt["loading_is_inert"] is True
    assert receipt["module_sha256"] == first["controller_sha256"]


def test_build_rejects_spawner_drift_and_existing_output(tmp_path: Path):
    spawner = tmp_path / "spawner_backend.lua"
    spawner.write_text("drift", encoding="utf-8")
    with pytest.raises(builder.SpawnSpanBuildError, match="Spawner source"):
        builder.build(
            spawner_source=spawner,
            modloader=MODLOADER,
            output_root=tmp_path / "out",
        )
