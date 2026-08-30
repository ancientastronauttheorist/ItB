"""Focused proofs for the build-keyed OpenGL shader interface census."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from scripts import itb_shader_census
from src.observatory.content_inventory import create_inventory
from src.observatory.shader_census import (
    ShaderCensusError,
    _canonical_sha256,
    build_shader_census,
    encode_shader_census,
    validate_shader_census,
)


_VERTEX_SOURCE = """
// RAW_SHADER_BODY_SENTINEL_MUST_NOT_BE_PUBLISHED
uniform mat4 viewProjMatrix;
attribute vec4 inPosition;
varying vec2 varyingTex0;
void main()
{
    gl_Position = viewProjMatrix * inPosition;
}
""".lstrip()

_FRAGMENT_SOURCE = """
#ifdef _ALPHA_TEST
uniform lowp vec4 alphaTestParams;
#endif
varying highp vec2 varyingTex0;
uniform sampler2D tex0;
void main()
{
    gl_FragColor = texture2D(tex0, varyingTex0);
#ifdef _ALPHA_TEST
    if (gl_FragColor.a < alphaTestParams.x) discard;
#endif
}
""".lstrip()


def _write_pe(path: Path, machine: int = 0x014C) -> None:
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<H", data, 132, machine)
    path.write_bytes(data)


def _installation(
    tmp_path: Path,
    *,
    vertex_source: str = _VERTEX_SOURCE,
) -> tuple[Path, dict]:
    steamapps = tmp_path / "Steam/steamapps"
    root = steamapps / "common/Into the Breach"
    (root / "scripts").mkdir(parents=True)
    (root / "maps").mkdir()
    (root / "shadersOGL").mkdir()
    (root / "scripts/bootstrap.lua").write_text(
        "return true\n", encoding="utf-8", newline="\n"
    )
    (root / "maps/synthetic.map").write_text(
        "Synthetic = {}\n", encoding="utf-8", newline="\n"
    )
    (root / "shadersOGL/basic.vs").write_text(
        vertex_source, encoding="utf-8", newline=""
    )
    (root / "shadersOGL/basic.ps").write_text(
        _FRAGMENT_SOURCE, encoding="utf-8", newline=""
    )
    _write_pe(root / "Breach.exe")
    (steamapps / "appmanifest_590380.acf").write_text(
        '''
"AppState"
{
    "appid" "590380"
    "installdir" "Into the Breach"
    "buildid" "13725832"
    "InstalledDepots"
    {
        "590381" { "manifest" "123456789" "size" "1" }
    }
}
''',
        encoding="utf-8",
        newline="\n",
    )
    inventory = create_inventory(
        root,
        platform_name="windows",
        label="synthetic-shader-census",
    )
    return root, inventory


def test_shader_census_is_deterministic_and_source_free(tmp_path: Path):
    root, inventory = _installation(tmp_path)
    result = build_shader_census(root, inventory=inventory)

    assert result["analysis_kind"] == "itb_opengl_shader_interface_census"
    assert result["summary"] == {
        "shader_files": 2,
        "shader_bytes": len(_VERTEX_SOURCE.encode())
        + len(_FRAGMENT_SOURCE.encode()),
        "stage_hints": [
            {"stage": "fragment_stage_hint", "files": 1},
            {"stage": "vertex_stage_hint", "files": 1},
        ],
        "entry_points": 2,
        "interface_declarations": 6,
        "interface_identifiers": 5,
        "uniform_identifiers": 3,
        "attribute_identifiers": 1,
        "varying_identifiers": 1,
        "preprocessor_symbols": 1,
        "call_identifiers": 1,
        "texture2d_calls": 1,
        "discard_occurrences": 1,
        "duplicate_content_groups": 0,
        "mixed_line_ending_files": 0,
        "schema_violations": 0,
    }
    rendered = encode_shader_census(result)
    assert "RAW_SHADER_BODY_SENTINEL_MUST_NOT_BE_PUBLISHED" not in rendered
    assert "gl_Position = viewProjMatrix * inPosition" not in rendered
    assert "gl_FragColor = texture2D" not in rendered
    assert "#ifdef" not in rendered

    rebuilt = build_shader_census(root, inventory=inventory)
    assert rebuilt == result
    verification = validate_shader_census(
        root,
        result,
        inventory=inventory,
    )
    assert verification["status"] == "verified"
    assert verification["evidence_sha256"] == _canonical_sha256(result)


def test_shader_manifest_seals_files_ignored_by_baseline_inventory(tmp_path: Path):
    root, inventory = _installation(tmp_path)
    result = build_shader_census(root, inventory=inventory)

    shader = root / "shadersOGL/basic.vs"
    shader.write_text(_VERTEX_SOURCE + "\n", encoding="utf-8", newline="")
    assert create_inventory(
        root,
        platform_name="windows",
        label="synthetic-shader-census",
    ) == inventory
    changed = build_shader_census(root, inventory=inventory)
    assert changed["shader_manifest"] != result["shader_manifest"]
    with pytest.raises(ShaderCensusError, match="does not match the exact"):
        validate_shader_census(root, result, inventory=inventory)


@pytest.mark.parametrize(
    "source, message",
    [
        ("uniform vec4 colors[2];\nvoid main(){}\n", "declaration shape"),
        ("uniform vec4 color;\nvoid main(){\n", "unterminated brace"),
        ("#ifdef FLAG\nvoid main(){}\n", "unterminated preprocessor"),
        (
            "#ifdef FLAG\n#else\n#else\n#endif\nvoid main(){}\n",
            "malformed #else",
        ),
        ("#if\n#endif\nvoid main(){}\n", "conditional expression"),
        (
            "#if FLAG + OTHER\n#endif\nvoid main(){}\n",
            "conditional expression",
        ),
        ('void main(){ const char x = "secret"; }\n', "string literals"),
        ("\ufeffvoid main(){}\n", "UTF-8 BOM"),
        ("void helper(){}\nvoid main(){}\n", "unsupported top-level block"),
        ("const int hidden = 1;\nvoid main(){}\n", "top-level syntax"),
        ("*/\nvoid main(){}\n", "unmatched block-comment close"),
    ],
)
def test_shader_census_rejects_unsupported_source_shapes(
    tmp_path: Path,
    source: str,
    message: str,
):
    root, inventory = _installation(tmp_path, vertex_source=source)
    with pytest.raises(ShaderCensusError, match=message):
        build_shader_census(root, inventory=inventory)


def test_shader_census_rejects_invalid_utf8_and_directory_shapes(tmp_path: Path):
    root, inventory = _installation(tmp_path / "utf8")
    (root / "shadersOGL/basic.vs").write_bytes(b"\xff")
    with pytest.raises(ShaderCensusError, match="not UTF-8"):
        build_shader_census(root, inventory=inventory)

    root, inventory = _installation(tmp_path / "extension")
    (root / "shadersOGL/readme.txt").write_text("not a shader\n", encoding="utf-8")
    with pytest.raises(ShaderCensusError, match="manifest entry .* malformed"):
        build_shader_census(root, inventory=inventory)

    root, inventory = _installation(tmp_path / "nested")
    (root / "shadersOGL/nested").mkdir()
    with pytest.raises(ShaderCensusError, match="only direct regular files"):
        build_shader_census(root, inventory=inventory)

    root, inventory = _installation(tmp_path / "filename")
    (root / "shadersOGL/bad-name.vs").write_text("void main(){}\n", encoding="utf-8")
    with pytest.raises(ShaderCensusError, match="manifest entry .* malformed"):
        build_shader_census(root, inventory=inventory)


def test_shader_census_handles_cr_only_line_comments(tmp_path: Path):
    root, inventory = _installation(
        tmp_path,
        vertex_source="// masked comment\rvoid main(){}\r",
    )
    result = build_shader_census(root, inventory=inventory)
    vertex = next(file for file in result["files"] if file["extension"] == ".vs")
    assert vertex["entry_points"] == ["main"]
    assert vertex["line_endings"] == {
        "style": "cr",
        "crlf": 0,
        "lf": 0,
        "cr": 2,
    }


def test_shader_census_rejects_symlinked_entries_when_supported(tmp_path: Path):
    root, inventory = _installation(tmp_path)
    link = root / "shadersOGL/linked.vs"
    try:
        link.symlink_to(root / "shadersOGL/basic.vs")
    except (NotImplementedError, OSError):
        pytest.skip("test host does not permit symlink creation")
    with pytest.raises(ShaderCensusError, match="only direct regular files"):
        build_shader_census(root, inventory=inventory)


def test_cli_atomic_writer_is_confined_and_kind_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    output_root = tmp_path / "shaders"
    monkeypatch.setattr(itb_shader_census, "_OUTPUT_ROOT", output_root)
    destination = output_root / "census.json"
    rendered = json.dumps(
        {"analysis_kind": "itb_opengl_shader_interface_census"},
        sort_keys=True,
    ) + "\n"
    itb_shader_census._write_evidence_atomically(destination, rendered)
    assert destination.read_text(encoding="utf-8") == rendered

    destination.write_text(
        json.dumps({"analysis_kind": "something_else"}),
        encoding="utf-8",
    )
    with pytest.raises(ShaderCensusError, match="non-shader-census"):
        itb_shader_census._write_evidence_atomically(destination, rendered)
    with pytest.raises(ShaderCensusError, match="direct child"):
        itb_shader_census._write_evidence_atomically(
            output_root / "nested/census.json",
            rendered,
        )
