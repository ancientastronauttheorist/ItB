from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_itb_observatory_spawn_replay_controller as builder


ROOT = Path(__file__).resolve().parents[1]
MODLOADER = ROOT / "src" / "bridge" / "modloader.lua"


def test_build_is_content_addressed_and_pins_both_shipped_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    spawner = tmp_path / "scripts" / "spawner_backend.lua"
    global_lua = tmp_path / "scripts" / "global.lua"
    spawner.parent.mkdir()
    spawner.write_bytes(b"exact pinned spawner\n")
    global_lua.write_bytes(b"exact pinned global\n")
    spawner_payload = spawner.read_bytes()
    global_payload = global_lua.read_bytes()
    real_sha256 = builder._sha256

    def pinned_hash(payload: bytes) -> str:
        if payload == spawner_payload:
            return builder.SPAWNER_SHA256
        if payload == global_payload:
            return builder.RANDOM_ELEMENT_SHA256
        return real_sha256(payload)

    monkeypatch.setattr(builder, "_sha256", pinned_hash)
    result = builder.build(
        spawner_source=spawner,
        global_source=global_lua,
        modloader=MODLOADER,
        output_root=tmp_path / "output",
    )

    module = Path(result["module"])
    receipt = json.loads(Path(result["receipt"]).read_text(encoding="utf-8"))
    assert module.read_bytes() == builder.SOURCE.read_bytes()
    assert receipt["loading_is_inert"] is True
    assert receipt["module_sha256"] == result["controller_sha256"]
    assert receipt["spawner_source_sha256"] == builder.SPAWNER_SHA256
    assert receipt["global_source_sha256"] == builder.RANDOM_ELEMENT_SHA256


def test_build_rejects_either_source_drift(tmp_path: Path):
    spawner = tmp_path / "spawner_backend.lua"
    global_lua = tmp_path / "global.lua"
    spawner.write_text("drift", encoding="utf-8")
    global_lua.write_text("drift", encoding="utf-8")
    with pytest.raises(builder.SpawnReplayBuildError, match="Spawner source"):
        builder.build(
            spawner_source=spawner,
            global_source=global_lua,
            modloader=MODLOADER,
            output_root=tmp_path / "out",
        )
