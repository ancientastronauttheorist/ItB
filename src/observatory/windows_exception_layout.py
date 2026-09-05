"""Independent x86 Windows SDK layout probe and finite frame compatibility map."""

from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from src.observatory import native_assertion_helper_frame_stores as stores
from src.observatory import native_assertion_helper_import_handoff as handoff
from src.observatory.native_assertion_helper_fill_conformance import (
    _canonical_bytes,
    _canonical_sha256,
    _source_identity,
    _validate_json_tree,
    _assert_publication_safe,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "windows_x86_exception_layout_compatibility"
SEALED_SHA256 = "c71a3142e5fc172a6a686a1b83f3bce3a9af181142c8386276ed481f2861acef"
SOURCE_PINS = {
    "stores": (stores.ANALYSIS_KIND, stores.SEALED_SHA256),
    "handoff": (handoff.ANALYSIS_KIND, handoff.SEALED_SHA256),
}
MSVC_VERSION = "14.29.30133"
SDK_VERSION = "10.0.19041.0"
MSVC = (
    Path(
        r"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Tools\MSVC"
    )
    / MSVC_VERSION
)
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
BIN = MSVC / "bin/Hostx64/x86"
HEADER = SDK / "Include" / SDK_VERSION / "um/winnt.h"
FILE_PINS = {
    "cl.exe": (
        BIN / "cl.exe",
        "33d0e40a63959649c8a6d400ab3786a78b4fce2a4f6b7215a47844c194ad314d",
    ),
    "link.exe": (
        BIN / "link.exe",
        "86fb8566bbdb587311c5754357df1f7905cc6a811731c0864293da8d659cf673",
    ),
    "winnt.h": (
        HEADER,
        "b6516692d618a7fbc3c8af93aa3edfd607428e6a0313114d422e2d79d1f6f75c",
    ),
}
# Authored independently of probe output. Offsets and widths are decimal bytes.
CONTEXT_FIELDS = [
    ("ContextFlags", 0, 4),
    ("Dr0", 4, 4),
    ("Dr1", 8, 4),
    ("Dr2", 12, 4),
    ("Dr3", 16, 4),
    ("Dr6", 20, 4),
    ("Dr7", 24, 4),
    ("FloatSave", 28, 112),
    ("SegGs", 140, 4),
    ("SegFs", 144, 4),
    ("SegEs", 148, 4),
    ("SegDs", 152, 4),
    ("Edi", 156, 4),
    ("Esi", 160, 4),
    ("Ebx", 164, 4),
    ("Edx", 168, 4),
    ("Ecx", 172, 4),
    ("Eax", 176, 4),
    ("Ebp", 180, 4),
    ("Eip", 184, 4),
    ("SegCs", 188, 4),
    ("EFlags", 192, 4),
    ("Esp", 196, 4),
    ("SegSs", 200, 4),
    ("ExtendedRegisters", 204, 512),
]
RECORD_FIELDS = [
    ("ExceptionCode", 0, 4),
    ("ExceptionFlags", 4, 4),
    ("ExceptionRecord", 8, 4),
    ("ExceptionAddress", 12, 4),
    ("NumberParameters", 16, 4),
    ("ExceptionInformation", 20, 60),
]
POINTER_FIELDS = [("ExceptionRecord", 0, 4), ("ContextRecord", 4, 4)]


class LayoutError(RuntimeError):
    """A pinned SDK layout, probe measurement, or receipt join differs."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise LayoutError(message)


def _normalize(fn: Any) -> Any:
    try:
        return fn()
    except LayoutError:
        raise
    except Exception as exc:
        raise LayoutError(str(exc)) from exc


def sdk_layout_spec() -> dict[str, Any]:
    structures = {}
    for name, size, fields in (
        ("CONTEXT", 716, CONTEXT_FIELDS),
        ("EXCEPTION_RECORD", 80, RECORD_FIELDS),
        ("EXCEPTION_POINTERS", 8, POINTER_FIELDS),
    ):
        _require(
            sum(w for _, _, w in fields) == size
            and [o for _, o, _ in fields]
            == [sum(w for _, _, w in fields[:i]) for i in range(len(fields))],
            "SDK field partition differs",
        )
        structures[name] = {
            "size": size,
            "fields": [{"name": n, "offset": o, "width": w} for n, o, w in fields],
        }
    return {
        "pointer_size": 4,
        "constants": {"CONTEXT_CONTROL": 65537},
        "structures": structures,
    }


def frame_overlap_spec() -> dict[str, Any]:
    """Layout compatibility only; names do not identify game runtime objects."""
    layout = sdk_layout_spec()["structures"]
    starts = {"EXCEPTION_POINTERS": -808, "EXCEPTION_RECORD": -800, "CONTEXT": -720}
    fields = []
    temporary = []
    for offset, width, source in stores.FIELDS:
        if offset == -816:
            temporary.append({"frame_offset": offset, "width": width, "source": source})
            continue
        matches = [
            (name, field)
            for name, start in starts.items()
            for field in layout[name]["fields"]
            if offset == start + field["offset"] and width <= field["width"]
        ]
        _require(len(matches) == 1, "frame store has no unique SDK field match")
        name, field = matches[0]
        fields.append(
            {
                "frame_offset": offset,
                "store_width": width,
                "source": source,
                "sdk_structure": name,
                "sdk_field": field["name"],
                "field_offset": field["offset"],
                "field_width": field["width"],
                "unwritten_upper_bytes": field["width"] - width,
            }
        )
    _require(
        len(fields) == 22 and sum(f["store_width"] == 2 for f in fields) == 6,
        "frame overlap partition differs",
    )
    return {
        "coordinate": "offset from established caller EBP",
        "regions": [
            {"sdk_structure": n, "frame_start": s, "frame_end": s + layout[n]["size"]}
            for n, s in starts.items()
        ],
        "stores": fields,
        "temporary_outside_records": temporary,
        "zero_regions": [
            {"sdk_structure": "EXCEPTION_RECORD", "frame_start": -800, "length": 80},
            {"sdk_structure": "CONTEXT", "frame_start": -720, "length": 716},
        ],
        "selector_store_interpretation": "Six two-byte stores occupy low halves of four-byte SDK DWORD fields; upper halves retain prior zero fill",
        "pointer_values": [
            {
                "frame_offset": -808,
                "points_to_frame_offset": -800,
                "compatible_pointee": "EXCEPTION_RECORD",
            },
            {
                "frame_offset": -804,
                "points_to_frame_offset": -720,
                "compatible_pointee": "CONTEXT",
            },
        ],
        "context_flags_constant": {
            "frame_offset": -720,
            "value": 65537,
            "sdk_macro": "CONTEXT_CONTROL",
        },
    }


def _preflight(sources: Mapping[str, Any]) -> dict[str, Any]:
    _validate_json_tree(sources, "sources")
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    ids = {
        k: _source_identity(sources[k], kind, digest, k)
        for k, (kind, digest) in SOURCE_PINS.items()
    }
    _require(
        sources["stores"]["overlay_fields"]
        == [{"offset": o, "width": w, "source": s} for o, w, s in stores.FIELDS],
        "frame overlay source differs",
    )
    _require(
        sources["handoff"]["prefix"]["exclusive_stop_rva"] == "0x00379e20",
        "handoff boundary differs",
    )
    return ids


def probe_source() -> str:
    # Only our sizeof and offsetof requests are generated; no SDK contents copied.
    lines = [
        "#include <windows.h>",
        "#include <stddef.h>",
        "#include <stdio.h>",
        '#define FIELD(T,N) printf("%s.%s=%u,%u\\n", #T, #N, (unsigned)offsetof(T,N), (unsigned)sizeof(((T*)0)->N))',
        "int main(void) {",
        'printf("pointer=%u\\nCONTEXT_CONTROL=%u\\n", (unsigned)sizeof(void*), (unsigned)CONTEXT_CONTROL);',
    ]
    for name, fields in (
        ("CONTEXT", CONTEXT_FIELDS),
        ("EXCEPTION_RECORD", RECORD_FIELDS),
        ("EXCEPTION_POINTERS", POINTER_FIELDS),
    ):
        lines.append(f'printf("{name}=%u\\n", (unsigned)sizeof({name}));')
        lines.extend(f"FIELD({name},{n});" for n, _, _ in fields)
    return "\n".join(lines + ["return 0;", "}", ""])


def parse_probe(text: str) -> dict[str, Any]:
    _require(type(text) is str and len(text) < 16384, "invalid probe output")
    measured = {}
    for line in text.splitlines():
        match = re.fullmatch(
            r"([A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)?)=([0-9]+)(?:,([0-9]+))?",
            line,
        )
        _require(match is not None, "malformed probe line")
        key, first, second = match.groups()
        _require(key not in measured, "duplicate probe measurement")
        measured[key] = int(first) if second is None else [int(first), int(second)]
    expected = {"pointer": 4, "CONTEXT_CONTROL": 65537}
    for name, structure in sdk_layout_spec()["structures"].items():
        expected[name] = structure["size"]
        expected.update(
            {
                name + "." + f["name"]: [f["offset"], f["width"]]
                for f in structure["fields"]
            }
        )
    _require(measured == expected, "SDK layout measurement differs")
    return measured


def _pinned_files() -> dict[str, str]:
    actual = {
        n: hashlib.sha256(p.read_bytes()).hexdigest() for n, (p, _) in FILE_PINS.items()
    }
    _require(
        actual == {n: d for n, (_, d) in FILE_PINS.items()},
        "toolchain or SDK header identity differs",
    )
    return actual


def _probe() -> dict[str, Any]:
    _require(os.name == "nt", "SDK measurement requires Windows")
    before = _pinned_files()
    root = Path(__file__).resolve().parents[2] / ".local_decompile/sdk_layout"
    root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="receipt-", dir=root)).resolve()
    _require(work.parent == root.resolve(), "probe work directory escaped root")
    source = probe_source()
    (work / "probe.c").write_text(source, encoding="ascii")
    env = dict(os.environ)
    for key in list(env):
        if key.upper() in {"CL", "_CL_", "LINK", "_LINK_", "INCLUDE", "LIB", "LIBPATH"}:
            del env[key]
    env["PATH"] = (
        str(BIN) + os.pathsep + str(Path(os.environ["SystemRoot"]) / "System32")
    )
    env["VSLANG"] = "1033"
    env["LIB"] = os.pathsep.join(
        str(p)
        for p in (
            MSVC / "lib/x86",
            SDK / "Lib" / SDK_VERSION / "ucrt/x86",
            SDK / "Lib" / SDK_VERSION / "um/x86",
        )
    )
    includes = [MSVC / "include"] + [
        SDK / "Include" / SDK_VERSION / name
        for name in ("ucrt", "shared", "um", "winrt")
    ]
    command = [
        str(BIN / "cl.exe"),
        "/nologo",
        "/W4",
        "/X",
        "/showIncludes",
        "/MT",
        "/TC",
        "/Fe:probe.exe",
        "/Fo:probe.obj",
    ]
    for path in includes:
        command.extend(["/I", str(path)])
    command.extend(["probe.c", "/link", "/MACHINE:X86"])
    compiled = subprocess.run(
        command, cwd=work, env=env, capture_output=True, timeout=60
    )
    (work / "compile.stdout").write_bytes(compiled.stdout)
    (work / "compile.stderr").write_bytes(compiled.stderr)
    _require(
        compiled.returncode == 0,
        "fixed SDK probe compilation failed; private logs retained",
    )
    include_paths = []
    for line in (
        (compiled.stdout + compiled.stderr)
        .decode("utf-8", errors="replace")
        .splitlines()
    ):
        if line.startswith("Note: including file:"):
            include_paths.append(
                Path(line.split("Note: including file:", 1)[1].strip()).resolve()
            )
    _require(
        HEADER.resolve() in include_paths,
        "compiler did not include pinned winnt header",
    )
    closure = []
    for path in sorted(set(include_paths), key=lambda p: str(p).lower()):
        label = None
        for name, base in (
            ("sdk", SDK / "Include" / SDK_VERSION),
            ("msvc", MSVC / "include"),
        ):
            if path.is_relative_to(base.resolve()):
                label = {
                    "root": name,
                    "components": list(path.relative_to(base.resolve()).parts),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
                break
        _require(label is not None, "included header outside pinned include roots")
        closure.append(label)
    ran = subprocess.run(
        [str(work / "probe.exe")], cwd=work, env=env, capture_output=True, timeout=15
    )
    (work / "layout.txt").write_bytes(ran.stdout)
    _require(ran.returncode == 0 and not ran.stderr, "fixed SDK probe execution failed")
    measured = parse_probe(ran.stdout.decode("ascii"))
    _require(_pinned_files() == before, "toolchain changed during probe")
    return {
        "file_sha256": before,
        "include_closure": closure,
        "measurements": measured,
        "probe_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
    }


def _build_unsealed(sources: Mapping[str, Any]) -> dict[str, Any]:
    ids = _preflight(sources)
    measured = _probe()
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "source_receipts": ids,
        "sdk_layout": sdk_layout_spec(),
        "frame_overlap": frame_overlap_spec(),
        "probe": measured,
        "configuration": {
            "msvc_tools_version": MSVC_VERSION,
            "compiler_version": "19.29.30154.0",
            "sdk_version": SDK_VERSION,
            "host_architecture": "x64",
            "target_architecture": "x86",
            "language": "C",
            "packing": "default compiler option with SDK header packing directives",
            "compiler_options": ["nologo", "W4", "X", "showIncludes", "MT", "TC"],
            "linker_options": ["MACHINE X86"],
            "runtime": "static multithreaded",
            "inherited_compiler_options": False,
            "include_search": "only fixed MSVC and SDK include directories",
            "pointer_size_required": 4,
        },
        "public_metadata": {
            "publisher": "Microsoft Learn",
            "header": "winnt.h",
            "page_ids": [
                "ns-winnt-context-r2",
                "ns-winnt-exception_record",
                "ns-winnt-exception_pointers",
            ],
        },
        "summary": {
            "structures": 3,
            "measured_fields": 33,
            "mapped_frame_stores": 22,
            "partial_dword_selector_stores": 6,
            "temporary_stores_outside_records": 1,
            "record_bytes": 80,
            "context_bytes": 716,
            "pointer_pair_bytes": 8,
        },
        "scope": {
            "claim": "Exact selected SDK x86 sizeof and offsetof measurements match independently authored layout; finite frame stores are byte-layout compatible",
            "not_claimed": [
                "The game was compiled with this compiler or SDK",
                "Runtime record identity or API consumption before an exact import-call handoff",
                "Original context capture semantics or initialized validity of every SDK field",
                "Native C object validity or alignment of every synthetic frame address",
                "Game execution, import execution, whole-function behavior or accounting promotion",
            ],
            "header_provenance": "Actual showIncludes dependency closure hashed; proprietary headers and compiler output remain private",
        },
    }
    _assert_publication_safe(result)
    return result


def validate_structure(
    evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        _validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256,
            "sealed SDK layout receipt differs",
        )
        _require(
            evidence["source_receipts"] == ids
            and evidence["sdk_layout"] == sdk_layout_spec()
            and evidence["frame_overlap"] == frame_overlap_spec(),
            "layout or source differs",
        )
        _assert_publication_safe(evidence)
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_layout(sources: Mapping[str, Any]) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        result = _build_unsealed(sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_layout(
    evidence: Mapping[str, Any], sources: Mapping[str, Any]
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        validate_structure(evidence, sources)
        actual = build_layout(sources)
        _require(
            _canonical_bytes(evidence) == _canonical_bytes(actual),
            "exact SDK probe replay differs",
        )
        return {
            "status": "verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(actual["summary"]),
        }

    return _normalize(run)


def encode_layout(value: Mapping[str, Any]) -> str:
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
