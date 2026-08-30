"""Focused proofs for the build-keyed FMOD bank/native interface census."""

from __future__ import annotations

import copy
import hashlib
import json
import struct
from pathlib import Path, PurePosixPath

import pytest

from scripts import itb_fmod_census
from src.observatory import fmod_census
from src.observatory.content_inventory import create_inventory
from src.observatory.fmod_census import (
    BANK_PATHS,
    FmodCensusError,
    _canonical_sha256,
    _pe_named_exports,
    _scan_bank,
    _version_resource_facts,
    build_fmod_census,
    encode_fmod_census,
    validate_fmod_census,
)
from src.observatory.pe_anchor_map import PEImage


_AUDIO_SENTINEL = b"DO_NOT_PUBLISH_AUDIO_PAYLOAD_BYTES"
_STRING_SENTINEL = b"event:/SECRET_EVENT_PATH_MUST_NOT_PUBLISH"


def _riff_chunk(chunk_id: bytes, payload: bytes, *, padding: bytes = b"\0") -> bytes:
    assert len(chunk_id) == 4
    result = chunk_id + struct.pack("<I", len(payload)) + payload
    if len(payload) & 1:
        result += padding
    return result


def _bank(*, strings_bank: bool = False, nonzero_padding: bool = False) -> bytes:
    fmt = _riff_chunk(b"FMT ", struct.pack("<II", 99, 99))
    if strings_bank:
        child = _riff_chunk(
            b"STDT",
            _STRING_SENTINEL,
            padding=b"\1" if nonzero_padding else b"\0",
        )
    else:
        child = _riff_chunk(b"WAV ", b"")
    metadata = _riff_chunk(b"LIST", b"TEST" + child)
    chunks = fmt + metadata
    if not strings_bank:
        audio = _AUDIO_SENTINEL
        if len(audio) & 1:
            audio += b"X"
        fsb_header = bytearray(60)
        fsb_header[:4] = b"FSB5"
        struct.pack_into("<5I", fsb_header, 4, 1, 1, len(audio), 0, 0)
        chunks += _riff_chunk(b"SND ", bytes(fsb_header) + audio)
    body = b"FEV " + chunks
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _pad4(value: bytearray) -> None:
    value.extend(b"\0" * ((-len(value)) & 3))


def _version_block(
    key: str,
    *,
    value: bytes = b"",
    value_type: int,
    children: tuple[bytes, ...] = (),
) -> bytes:
    result = bytearray(b"\0" * 6)
    result.extend((key + "\0").encode("utf-16-le"))
    _pad4(result)
    result.extend(value)
    if children:
        _pad4(result)
        for index, child in enumerate(children):
            if index:
                _pad4(result)
            result.extend(child)
    value_length = len(value) // 2 if value_type == 1 else len(value)
    struct.pack_into("<HHH", result, 0, len(result), value_length, value_type)
    return bytes(result)


def _text_version_block(key: str, value: str) -> bytes:
    return _version_block(
        key,
        value=(value + "\0").encode("utf-16-le"),
        value_type=1,
    )


def _version_blob(filename: str) -> bytes:
    table = _version_block(
        "040904B0",
        value_type=1,
        children=(
            _text_version_block("FileVersion", "1.2.3 (build 45)"),
            _text_version_block("ProductVersion", "1.2.3"),
            _text_version_block("OriginalFilename", filename),
        ),
    )
    strings = _version_block(
        "StringFileInfo",
        value_type=1,
        children=(table,),
    )
    fixed_words = (
        0xFEEF04BD,
        0x00010000,
        1,
        (2 << 16) | 3,
        1,
        (2 << 16) | 3,
        0x3F,
        0,
        0x00040004,
        1,
        0,
        0,
        0,
    )
    return _version_block(
        "VS_VERSION_INFO",
        value=struct.pack("<13I", *fixed_words),
        value_type=0,
        children=(strings,),
    )


class _Section:
    def __init__(self) -> None:
        self.data = bytearray(b"\x90" * 16)

    def align(self, boundary: int) -> None:
        self.data.extend(b"\0" * ((-len(self.data)) & (boundary - 1)))

    def add(self, payload: bytes, *, alignment: int = 1) -> int:
        self.align(alignment)
        offset = len(self.data)
        self.data.extend(payload)
        return offset

    @staticmethod
    def rva(offset: int) -> int:
        return 0x1000 + offset


def _add_exports(
    section: _Section,
    names: list[str],
    *,
    ordinal_indices: list[int] | None = None,
    function_rvas: list[int] | None = None,
) -> tuple[int, int]:
    section.align(4)
    start = len(section.data)
    name_count = len(names)
    if ordinal_indices is None:
        ordinal_indices = list(range(name_count))
    if function_rvas is None:
        function_rvas = [0x1000] * name_count
    assert len(ordinal_indices) == name_count
    function_count = len(function_rvas)
    functions_relative = 40
    names_relative = functions_relative + function_count * 4
    ordinals_relative = names_relative + name_count * 4
    strings_relative = ordinals_relative + name_count * 2
    region = bytearray(strings_relative)
    module_relative = len(region)
    region.extend(b"synthetic.dll\0")
    name_relatives = []
    for name in names:
        name_relatives.append(len(region))
        region.extend(name.encode("ascii") + b"\0")
    for index, function_rva in enumerate(function_rvas):
        struct.pack_into("<I", region, functions_relative + index * 4, function_rva)
    for index, relative in enumerate(name_relatives):
        struct.pack_into(
            "<I", region, names_relative + index * 4, section.rva(start + relative)
        )
        struct.pack_into(
            "<H", region, ordinals_relative + index * 2, ordinal_indices[index]
        )
    struct.pack_into(
        "<IIHHIIIIIII",
        region,
        0,
        0,
        0,
        0,
        0,
        section.rva(start + module_relative),
        1,
        function_count,
        name_count,
        section.rva(start + functions_relative),
        section.rva(start + names_relative),
        section.rva(start + ordinals_relative),
    )
    section.data.extend(region)
    return section.rva(start), len(region)


def _add_version_resource(section: _Section, filename: str) -> tuple[int, int]:
    version = _version_blob(filename)
    section.align(4)
    start = len(section.data)
    resource = bytearray(0x80)
    struct.pack_into("<IIHHHH", resource, 0, 0, 0, 0, 0, 0, 1)
    struct.pack_into("<II", resource, 16, 16, 0x80000020)
    struct.pack_into("<IIHHHH", resource, 0x20, 0, 0, 0, 0, 0, 1)
    struct.pack_into("<II", resource, 0x30, 1, 0x80000040)
    struct.pack_into("<IIHHHH", resource, 0x40, 0, 0, 0, 0, 0, 1)
    struct.pack_into("<II", resource, 0x50, 1033, 0x60)
    struct.pack_into(
        "<IIII",
        resource,
        0x60,
        section.rva(start + 0x80),
        len(version),
        1200,
        0,
    )
    resource.extend(version)
    section.data.extend(resource)
    return section.rva(start), len(resource)


def _add_imports(
    section: _Section,
    imports: dict[str, list[str | int]],
) -> tuple[int, int]:
    section.align(4)
    start = len(section.data)
    descriptor_count = len(imports) + 1
    section.data.extend(b"\0" * (descriptor_count * 20))
    for descriptor_index, (library, names) in enumerate(imports.items()):
        library_offset = section.add(library.encode("ascii") + b"\0")
        thunk_values = []
        for hint, name in enumerate(names):
            if isinstance(name, int):
                thunk_values.append(0x80000000 | name)
            else:
                entry_offset = section.add(
                    struct.pack("<H", hint) + name.encode("ascii") + b"\0",
                    alignment=2,
                )
                thunk_values.append(section.rva(entry_offset))
        lookup_offset = section.add(
            struct.pack(f"<{len(thunk_values) + 1}I", *thunk_values, 0),
            alignment=4,
        )
        iat_offset = section.add(
            struct.pack(f"<{len(thunk_values) + 1}I", *thunk_values, 0),
            alignment=4,
        )
        struct.pack_into(
            "<IIIII",
            section.data,
            start + descriptor_index * 20,
            section.rva(lookup_offset),
            0,
            0,
            section.rva(library_offset),
            section.rva(iat_offset),
        )
    return section.rva(start), descriptor_count * 20


def _pe(
    *,
    exports: list[str] | None = None,
    export_ordinals: list[int] | None = None,
    export_function_rvas: list[int] | None = None,
    version_filename: str | None = None,
    imports: dict[str, list[str | int]] | None = None,
    literals: tuple[str, ...] = (),
) -> bytes:
    section = _Section()
    directories: dict[int, tuple[int, int]] = {}
    if exports is not None:
        directories[0] = _add_exports(
            section,
            exports,
            ordinal_indices=export_ordinals,
            function_rvas=export_function_rvas,
        )
    if version_filename is not None:
        directories[2] = _add_version_resource(section, version_filename)
    if imports is not None:
        directories[1] = _add_imports(section, imports)
    for literal in literals:
        section.add(literal.encode("ascii") + b"\0", alignment=4)

    virtual_size = len(section.data)
    raw_size = (virtual_size + 0x1FF) & ~0x1FF
    data = bytearray(0x200 + raw_size)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into(
        "<HHIIIHH",
        data,
        0x84,
        0x014C,
        1,
        0x12345678,
        0,
        0,
        0xE0,
        0x210E,
    )
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x10B)
    struct.pack_into("<I", data, optional + 16, 0x1000)
    struct.pack_into("<I", data, optional + 28, 0x400000)
    struct.pack_into("<I", data, optional + 32, 0x1000)
    struct.pack_into("<I", data, optional + 36, 0x200)
    struct.pack_into("<I", data, optional + 56, 0x2000)
    struct.pack_into("<I", data, optional + 60, 0x200)
    struct.pack_into("<I", data, optional + 92, 16)
    for index, (rva, size) in directories.items():
        struct.pack_into("<II", data, optional + 96 + index * 8, rva, size)
    section_header = optional + 0xE0
    data[section_header : section_header + 8] = b".rdata\0\0"
    struct.pack_into(
        "<IIII",
        data,
        section_header + 8,
        virtual_size,
        0x1000,
        raw_size,
        0x200,
    )
    struct.pack_into("<I", data, section_header + 36, 0x40000040)
    data[0x200 : 0x200 + virtual_size] = section.data
    return bytes(data)


def _installation(tmp_path: Path) -> tuple[Path, dict]:
    steamapps = tmp_path / "Steam/steamapps"
    root = steamapps / "common/Into the Breach"
    (root / "scripts").mkdir(parents=True)
    (root / "maps").mkdir()
    (root / "resources").mkdir()
    (root / "scripts/bootstrap.lua").write_text("return true\n", encoding="utf-8")
    (root / "maps/synthetic.map").write_text("Synthetic = {}\n", encoding="utf-8")
    for relative in BANK_PATHS:
        (root / relative).write_bytes(
            _bank(strings_bank=relative.endswith(".strings.bank"))
        )
    fmod_exports = ["FMOD_System_GetVersion"]
    studio_exports = ["FMOD_Studio_System_Create", "FMOD_Studio_System_LoadBankFile"]
    (root / "fmod.dll").write_bytes(
        _pe(exports=fmod_exports, version_filename="fmod.dll")
    )
    (root / "fmodstudio.dll").write_bytes(
        _pe(exports=studio_exports, version_filename="fmodstudio.dll")
    )
    (root / "Breach.exe").write_bytes(
        _pe(
            imports={
                "fmod.dll": fmod_exports,
                "fmodstudio.dll": studio_exports,
            },
            literals=tuple(PurePosixPath(path).name for path in BANK_PATHS),
        )
    )
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
        label="synthetic-fmod-census",
    )
    return root, inventory


def test_fmod_census_is_deterministic_exact_and_payload_free(tmp_path: Path):
    root, inventory = _installation(tmp_path)
    result = build_fmod_census(root, inventory=inventory)

    bank_bytes = sum((root / path).stat().st_size for path in BANK_PATHS)
    assert result["summary"] == {
        "bank_files": 5,
        "bank_bytes": bank_bytes,
        "riff_nodes": 19,
        "top_level_chunks": 14,
        "recursive_wav_chunks": 4,
        "fsb5_signatures": 4,
        "native_libraries": 2,
        "named_exports": 3,
        "ordinal_only_exports": 0,
        "executable_named_imports": 3,
        "executable_ordinal_imports": 0,
        "bank_basename_literal_occurrences": 5,
        "schema_violations": 0,
    }
    manifest_files = [
        {key: bank[key] for key in ("path", "size", "sha256")}
        for bank in result["banks"]
    ]
    assert result["bank_manifest"]["canonical_sha256"] == _canonical_sha256(
        manifest_files
    )
    rendered = encode_fmod_census(result)
    assert _AUDIO_SENTINEL.decode() not in rendered
    assert _STRING_SENTINEL.decode() not in rendered
    assert str(tmp_path) not in rendered
    assert "payload_sha256" not in rendered
    assert '"event_paths"' not in rendered

    assert build_fmod_census(root, inventory=inventory) == result
    verification = validate_fmod_census(root, result, inventory=inventory)
    assert verification["status"] == "verified"
    assert verification["evidence_sha256"] == _canonical_sha256(result)


def test_verifier_uses_type_exact_canonical_comparison(tmp_path: Path):
    root, inventory = _installation(tmp_path)
    result = build_fmod_census(root, inventory=inventory)
    tampered = copy.deepcopy(result)
    tampered["banks"][0]["fmt_payload_u32le"][0] = True
    with pytest.raises(FmodCensusError, match="does not match the exact"):
        validate_fmod_census(root, tampered, inventory=inventory)


def test_bank_manifest_detects_changes_ignored_by_baseline(tmp_path: Path):
    root, inventory = _installation(tmp_path)
    result = build_fmod_census(root, inventory=inventory)
    target = root / BANK_PATHS[0]
    changed = bytearray(target.read_bytes())
    changed[-1] ^= 1
    target.write_bytes(changed)
    assert create_inventory(
        root,
        platform_name="windows",
        label="synthetic-fmod-census",
    ) == inventory
    rebuilt = build_fmod_census(root, inventory=inventory)
    assert rebuilt["bank_manifest"] != result["bank_manifest"]
    with pytest.raises(FmodCensusError, match="does not match the exact"):
        validate_fmod_census(root, result, inventory=inventory)


def test_bank_surface_rejects_missing_extra_nested_and_symlink(tmp_path: Path):
    root, inventory = _installation(tmp_path / "missing")
    (root / BANK_PATHS[0]).unlink()
    with pytest.raises(FmodCensusError, match="bank surface differs"):
        build_fmod_census(root, inventory=inventory)

    root, inventory = _installation(tmp_path / "extra")
    (root / "resources/extra.bank").write_bytes(_bank())
    with pytest.raises(FmodCensusError, match="bank surface differs"):
        build_fmod_census(root, inventory=inventory)

    root, inventory = _installation(tmp_path / "nested")
    (root / "resources/nested").mkdir()
    with pytest.raises(FmodCensusError, match="nested resources"):
        build_fmod_census(root, inventory=inventory)

    root, inventory = _installation(tmp_path / "symlink")
    link = root / "resources/linked.bank"
    try:
        link.symlink_to(root / BANK_PATHS[0])
    except (NotImplementedError, OSError):
        pytest.skip("test host does not permit symlink creation")
    with pytest.raises(FmodCensusError, match="link/reparse"):
        build_fmod_census(root, inventory=inventory)


def test_bank_surface_is_reenumerated_after_all_scans(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root, inventory = _installation(tmp_path)
    original_scan = fmod_census._scan_bank
    scanned = 0

    def scan_then_mutate(*args, **kwargs):
        nonlocal scanned
        result = original_scan(*args, **kwargs)
        scanned += 1
        if scanned == len(BANK_PATHS):
            (root / "resources/late.bank").write_bytes(_bank())
        return result

    monkeypatch.setattr(fmod_census, "_scan_bank", scan_then_mutate)
    with pytest.raises(FmodCensusError, match="bank surface differs"):
        build_fmod_census(root, inventory=inventory)


def test_bank_surface_enumeration_is_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root, inventory = _installation(tmp_path)
    monkeypatch.setattr(fmod_census, "MAX_RESOURCE_DIRECTORY_ENTRIES", 4)
    with pytest.raises(FmodCensusError, match="entry count"):
        build_fmod_census(root, inventory=inventory)


def test_bank_surface_is_rechecked_after_native_analysis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    root, inventory = _installation(tmp_path)
    original_scan = fmod_census._scan_library
    mutated = False

    def scan_then_mutate(*args, **kwargs):
        nonlocal mutated
        result = original_scan(*args, **kwargs)
        if not mutated:
            target = root / BANK_PATHS[0]
            changed = bytearray(target.read_bytes())
            changed[-1] ^= 1
            target.write_bytes(changed)
            mutated = True
        return result

    monkeypatch.setattr(fmod_census, "_scan_library", scan_then_mutate)
    with pytest.raises(FmodCensusError, match="bank surface changed"):
        build_fmod_census(root, inventory=inventory)


@pytest.mark.parametrize(
    "mutator, message",
    [
        (lambda value: b"NOPE" + value[4:], "not RIFF"),
        (
            lambda value: value[:4] + struct.pack("<I", len(value)) + value[8:],
            "declared size",
        ),
        (lambda value: value[:8] + b"NOPE" + value[12:], "form type"),
        (
            lambda value: value[:16] + struct.pack("<I", 0xFFFFFFFF) + value[20:],
            "escapes",
        ),
    ],
)
def test_bank_parser_rejects_malformed_riff(
    tmp_path: Path,
    mutator,
    message: str,
):
    path = tmp_path / "bank.bank"
    path.write_bytes(mutator(_bank()))
    with pytest.raises(FmodCensusError, match=message):
        _scan_bank(path, "resources/ambience.bank", tmp_path)


def test_bank_parser_rejects_nonzero_padding_and_bad_fsb_span(tmp_path: Path):
    strings = tmp_path / "strings.bank"
    strings.write_bytes(_bank(strings_bank=True, nonzero_padding=True))
    with pytest.raises(FmodCensusError, match="nonzero padding"):
        _scan_bank(strings, "resources/Master Bank.strings.bank", tmp_path)

    audio = tmp_path / "audio.bank"
    malformed = bytearray(_bank())
    fsb = malformed.index(b"FSB5")
    struct.pack_into("<I", malformed, fsb + 12, 1)
    audio.write_bytes(malformed)
    with pytest.raises(FmodCensusError, match="does not reach EOF"):
        _scan_bank(audio, "resources/ambience.bank", tmp_path)

    duplicate_signature = bytearray(_bank())
    sentinel_offset = duplicate_signature.index(_AUDIO_SENTINEL)
    duplicate_signature[sentinel_offset : sentinel_offset + 4] = b"FSB5"
    audio.write_bytes(duplicate_signature)
    with pytest.raises(FmodCensusError, match="signature count"):
        _scan_bank(audio, "resources/ambience.bank", tmp_path)


def test_pe_export_and_version_parsers_fail_closed():
    duplicate = _pe(
        exports=["FMOD_Duplicate", "FMOD_Duplicate"],
        version_filename="fmod.dll",
    )
    with pytest.raises(FmodCensusError, match="duplicate"):
        _pe_named_exports(duplicate, PEImage(duplicate))

    malformed = bytearray(_version_blob("fmod.dll"))
    signature = malformed.index(struct.pack("<I", 0xFEEF04BD))
    struct.pack_into("<I", malformed, signature, 0)
    with pytest.raises(FmodCensusError, match="signature"):
        _version_resource_facts(bytes(malformed), "fmod.dll")


def test_pe_export_parser_counts_aliases_and_ordinal_only_slots():
    image_bytes = _pe(
        exports=["FMOD_Primary", "FMOD_Alias"],
        export_ordinals=[0, 0],
        export_function_rvas=[0x1000, 0x1000],
    )
    facts, names, ordinals = _pe_named_exports(image_bytes, PEImage(image_bytes))
    assert names == {"FMOD_Primary", "FMOD_Alias"}
    assert ordinals == {1, 2}
    assert facts == {
        "function_slots": 2,
        "nonzero_function_slots": 2,
        "named_count": 2,
        "named_ordinal_slots": 1,
        "named_alias_count": 1,
        "ordinal_only_count": 1,
        "forwarder_count": 0,
        "sorted_named_identity_sha256": _canonical_sha256(sorted(names)),
    }

    invalid = _pe(
        exports=["FMOD_Primary"],
        export_ordinals=[0],
        export_function_rvas=[0x1000, 0x900000],
    )
    with pytest.raises(FmodCensusError, match="target is outside"):
        _pe_named_exports(invalid, PEImage(invalid))


def test_version_parser_requires_exact_hierarchy_and_text_terminator():
    wrong_hierarchy = bytearray(_version_blob("fmod.dll"))
    original_key = "StringFileInfo".encode("utf-16-le")
    replacement_key = "NestedFileInfo".encode("utf-16-le")
    assert len(original_key) == len(replacement_key)
    key_offset = wrong_hierarchy.index(original_key)
    wrong_hierarchy[key_offset : key_offset + len(original_key)] = replacement_key
    with pytest.raises(FmodCensusError, match="hierarchy"):
        _version_resource_facts(bytes(wrong_hierarchy), "fmod.dll")

    unterminated = bytearray(_version_blob("fmod.dll"))
    original_value = "1.2.3 (build 45)\0".encode("utf-16-le")
    value_offset = unterminated.index(original_value)
    unterminated[value_offset + len(original_value) - 2 : value_offset + len(
        original_value
    )] = "X".encode("utf-16-le")
    with pytest.raises(FmodCensusError, match="NUL-terminated"):
        _version_resource_facts(bytes(unterminated), "fmod.dll")

    bad_key_padding = bytearray(_version_blob("fmod.dll"))
    file_version_key = "FileVersion\0".encode("utf-16-le")
    padding_offset = bad_key_padding.index(file_version_key) + len(file_version_key)
    bad_key_padding[padding_offset] = 1
    with pytest.raises(FmodCensusError, match="key/value padding"):
        _version_resource_facts(bytes(bad_key_padding), "fmod.dll")

    trailing_padding = bytearray(_version_blob("fmod.dll"))
    trailing_padding.extend(b"\0" * 64)
    struct.pack_into("<H", trailing_padding, 0, len(trailing_padding))
    with pytest.raises(FmodCensusError, match="version block|child padding"):
        _version_resource_facts(bytes(trailing_padding), "fmod.dll")


def test_build_rejects_unresolved_import_and_stale_baseline(tmp_path: Path):
    root, inventory = _installation(tmp_path / "import")
    (root / "Breach.exe").write_bytes(
        _pe(
            imports={
                "fmod.dll": ["FMOD_Missing"],
                "fmodstudio.dll": ["FMOD_Studio_System_Create"],
            },
            literals=tuple(PurePosixPath(path).name for path in BANK_PATHS),
        )
    )
    stale = create_inventory(
        root,
        platform_name="windows",
        label="synthetic-fmod-census",
    )
    with pytest.raises(FmodCensusError, match="absent from sealed DLL exports"):
        build_fmod_census(root, inventory=stale)

    root, _inventory = _installation(tmp_path / "ordinal")
    (root / "Breach.exe").write_bytes(
        _pe(
            imports={
                "fmod.dll": [2],
                "fmodstudio.dll": ["FMOD_Studio_System_Create"],
            },
            literals=tuple(PurePosixPath(path).name for path in BANK_PATHS),
        )
    )
    ordinal_inventory = create_inventory(
        root,
        platform_name="windows",
        label="synthetic-fmod-census",
    )
    with pytest.raises(FmodCensusError, match="ordinal import is absent"):
        build_fmod_census(root, inventory=ordinal_inventory)

    root, inventory = _installation(tmp_path / "baseline")
    (root / "scripts/bootstrap.lua").write_text("changed\n", encoding="utf-8")
    with pytest.raises(FmodCensusError, match="does not match the supplied"):
        build_fmod_census(root, inventory=inventory)


def test_cli_json_reader_rejects_duplicates_floats_and_constants(tmp_path: Path):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"a": 1, "a": 2}', encoding="utf-8")
    with pytest.raises(FmodCensusError, match="duplicate JSON"):
        itb_fmod_census._read_json_object(duplicate, "duplicate")

    floating = tmp_path / "float.json"
    floating.write_text('{"a": 1.0}', encoding="utf-8")
    with pytest.raises(FmodCensusError, match="floating-point"):
        itb_fmod_census._read_json_object(floating, "float")

    constant = tmp_path / "constant.json"
    constant.write_text('{"a": NaN}', encoding="utf-8")
    with pytest.raises(FmodCensusError, match="invalid JSON constant"):
        itb_fmod_census._read_json_object(constant, "constant")


def test_cli_atomic_writer_is_confined_and_kind_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    output_root = repo_root / "data/observatory/fmod"
    monkeypatch.setattr(itb_fmod_census, "_REPO_ROOT", repo_root)
    monkeypatch.setattr(itb_fmod_census, "_OUTPUT_ROOT", output_root)
    destination = output_root / "census.json"
    rendered = json.dumps(
        {"analysis_kind": "itb_fmod_bank_interface_census"},
        sort_keys=True,
    ) + "\n"
    itb_fmod_census._write_evidence_atomically(destination, rendered)
    assert destination.read_text(encoding="utf-8") == rendered

    destination.write_text(
        json.dumps({"analysis_kind": "something_else"}),
        encoding="utf-8",
    )
    with pytest.raises(FmodCensusError, match="non-FMOD-census"):
        itb_fmod_census._write_evidence_atomically(destination, rendered)
    with pytest.raises(FmodCensusError, match="direct child"):
        itb_fmod_census._write_evidence_atomically(
            output_root / "nested/census.json",
            rendered,
        )


def test_cli_atomic_writer_rejects_linked_output_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    repo_root = tmp_path / "repo"
    output_parent = repo_root / "data/observatory"
    output_parent.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    output_root = output_parent / "fmod"
    try:
        output_root.symlink_to(external, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("test host does not permit directory symlinks")
    monkeypatch.setattr(itb_fmod_census, "_REPO_ROOT", repo_root)
    monkeypatch.setattr(itb_fmod_census, "_OUTPUT_ROOT", output_root)
    rendered = '{"analysis_kind":"itb_fmod_bank_interface_census"}\n'
    with pytest.raises(FmodCensusError, match="link/reparse"):
        itb_fmod_census._write_evidence_atomically(
            output_root / "census.json",
            rendered,
        )
    assert not (external / "census.json").exists()
