"""Safety boundary tests for the ITB inventory CLI."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import itb_content_inventory  # noqa: E402


def _installation(tmp_path: Path) -> Path:
    root = tmp_path / "game"
    (root / "scripts").mkdir(parents=True)
    (root / "maps").mkdir()
    (root / "scripts/global.lua").write_text("return 1")
    (root / "maps/a.map").write_text("map")
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<H", data, 132, 0x014C)
    (root / "Breach.exe").write_bytes(data)
    return root


def test_cli_refuses_output_inside_installed_game(tmp_path: Path, capsys):
    root = _installation(tmp_path)
    output = root / "observatory.json"
    result = itb_content_inventory.main(
        [
            "inventory",
            "--install-dir",
            str(root),
            "--output",
            str(output),
        ]
    )
    assert result == 2
    assert not output.exists()
    assert "refusing to write" in capsys.readouterr().err
