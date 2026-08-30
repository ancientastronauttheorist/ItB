"""Build-keyed compiled and lexical census of Into the Breach Lua 5.1.

Accepted Lua sources are compiled but never executed.  Lua 5.1 bytecode is
reduced to structural metadata, hashes, opcode counts, and identifier-only
global/member references.  Raw source, literal values, and bytecode are not
eligible for the normalized artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from src.observatory.content_inventory import (
    InventoryError,
    create_inventory,
    inspect_executable_format,
)
from src.observatory.lua51_bytecode import (
    OPCODE_NAMES,
    Lua51BytecodeError,
    Lua51Chunk,
    Lua51Prototype,
    flatten_prototypes,
    identifier_constant,
    instruction_b,
    instruction_bx,
    instruction_c,
    instruction_opcode,
    parse_lua51_chunk,
    rk_constant_index,
)
from src.observatory.pe_anchor_map import PEAnchorError, _inventory_identity
from src.observatory.weapon_coverage import (
    WeaponCoverageError,
    lua_brace_depths,
    lua_function_spans,
    mask_lua_opaque,
    read_exact_inventory_file,
    source_position,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "itb_lua51_compiled_census"
VERIFICATION_KIND = "itb_lua51_compiled_census_verification"
MAX_LUA_SOURCE_BYTES = 64 * 1024 * 1024
LOCAL_OVERLAY_PATHS = frozenset(
    {
        "scripts/modloader.lua",
        "scripts/modloader.lua.bak_20260608_213240",
        "scripts/modloader.lua.codex-backup",
        "scripts/modloader.lua.pre_safe_leap_20260601_003010",
    }
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_DECLARATION_NAME = rf"{_IDENTIFIER}(?:\.{_IDENTIFIER})*(?::{_IDENTIFIER})?"
_ASSIGNMENT_NAME = rf"{_IDENTIFIER}(?:\.{_IDENTIFIER})*"
_EXPLICIT_FUNCTION_RE = re.compile(
    rf"function[ \t\r\n]+(?P<name>{_DECLARATION_NAME})[ \t\r\n]*\("
)
_LOCAL_BEFORE_RE = re.compile(r"\blocal[ \t\r\n]*\Z")
_ASSIGNMENT_BEFORE_RE = re.compile(
    rf"(?:\A|[\n;,{{])[ \t\r\n]*(?P<local>local[ \t\r\n]+)?"
    rf"(?P<name>{_ASSIGNMENT_NAME})[ \t\r\n]*=[ \t\r\n]*\Z"
)
_MEMBER_RE = re.compile(
    rf"\b(?P<root>{_IDENTIFIER})[ \t\r\n]*"
    rf"(?P<separator>[.:])[ \t\r\n]*(?P<member>{_IDENTIFIER})\b"
)
_GLOBAL_TABLE_INDEX_RE = re.compile(r"\b_G[ \t\r\n]*\[")
_GLOBAL_TABLE_WRITE_RE = re.compile(
    r"\b_G[ \t\r\n]*\[[^\]]*\][ \t\r\n]*="
)
_LUA_PATH_VALUE_RE = re.compile(
    r"(?:scripts|user)/[A-Za-z0-9_./-]+\.lua\Z"
)
_DOFILE_PREFIX_RE = re.compile(
    r"\bdofile[ \t\r\n]*\([ \t\r\n]*"
    r"GetWorkingDir[ \t\r\n]*\([ \t\r\n]*\)[ \t\r\n]*"
    r"\.\."
)
_IDENTIFIER_BYTES_RE = re.compile(rb"[A-Za-z_][A-Za-z0-9_]*\Z")
_STANDARD_GLOBALS = frozenset(
    {
        "_G",
        "_VERSION",
        "assert",
        "collectgarbage",
        "coroutine",
        "debug",
        "dofile",
        "error",
        "gcinfo",
        "getfenv",
        "getmetatable",
        "io",
        "ipairs",
        "load",
        "loadfile",
        "loadstring",
        "math",
        "module",
        "newproxy",
        "next",
        "os",
        "package",
        "pairs",
        "pcall",
        "print",
        "rawequal",
        "rawget",
        "rawset",
        "require",
        "select",
        "setfenv",
        "setmetatable",
        "string",
        "table",
        "tonumber",
        "tostring",
        "type",
        "unpack",
        "xpcall",
    }
)
_LOADER_GLOBALS = frozenset({"dofile", "load", "loadfile", "loadstring", "require"})
_ANALYZED_DISPOSITIONS = frozenset(
    {
        "accepted_game_lua_analyzed",
        "accepted_map_bootstrap_lua_analyzed",
        "accepted_map_data_lua_analyzed",
    }
)
_METHOD = {
    "compiler_gate": (
        "each accepted source is compiled by a Lua 5.1 compiler and dumped "
        "without executing the compiled game chunk"
    ),
    "function_completeness": (
        "every compiled nested prototype is paired one-to-one with a lexical "
        "function/end span by exact prototype-tree shape and source line range"
    ),
    "global_semantics": (
        "GETGLOBAL and SETGLOBAL operands are decoded from Lua 5.1 instructions; "
        "these access a function environment that setfenv may redirect from _G; "
        "identifier field/method operands and lexical root.member forms are "
        "reported separately"
    ),
    "publication_boundary": (
        "the artifact contains paths, identifiers, spans, counts, and hashes; "
        "it omits source text, literal payloads, instruction sequences, and "
        "binary chunks"
    ),
    "load_graph": (
        "the direct literal table returned by GetScripts is cross-checked against "
        "the compiled function constant table; supported literal "
        "dofile(GetWorkingDir()..path) syntax sites are cross-checked against "
        "compiled GETGLOBAL dofile occurrences; none proves runtime reachability, "
        "and host bootstraps/map-directory discovery are labeled assumptions"
    ),
    "not_claimed": [
        "runtime reachability or load order",
        "effects of dynamic load/loadstring/dofile calls",
        "a complete runtime global namespace, including computed _G keys",
        "native registration equivalence",
        "whether an unresolved host global is implemented in C++ or Lua elsewhere",
        "control-flow or behavioral equivalence",
        "a pristine unmodified Steam-depot corpus",
    ],
}


class LuaCensusError(RuntimeError):
    """Raised when Lua census inputs or compiler evidence are untrustworthy."""


@dataclass
class _FunctionSpan:
    start: int
    end: int
    children: list["_FunctionSpan"] = field(default_factory=list)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LuaCensusError(f"{label} must be an object")
    return value


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256((rendered + "\n").encode("utf-8")).hexdigest()


def _build_identity(inventory: Mapping[str, Any]) -> dict[str, Any]:
    executable = _mapping(inventory.get("executable"), "inventory.executable")
    try:
        return _inventory_identity(
            inventory,
            sha256=executable["sha256"],
            size=executable["size"],
            architecture=executable["architecture"],
        )
    except (KeyError, PEAnchorError) as exc:
        raise LuaCensusError(f"invalid inventory identity: {exc}") from exc


def _attest_installation(
    install_root: Path,
    inventory: Mapping[str, Any],
) -> tuple[Path, dict[str, Any]]:
    platform_name = inventory.get("platform")
    label = inventory.get("label")
    if type(platform_name) is not str or not platform_name:
        raise LuaCensusError("inventory.platform must be text")
    if label is not None and type(label) is not str:
        raise LuaCensusError("inventory.label must be text or null")
    try:
        live_inventory = create_inventory(
            install_root,
            platform_name=platform_name,
            label=label,
        )
    except (InventoryError, OSError, UnicodeError) as exc:
        raise LuaCensusError(
            f"could not rebuild the installation inventory: {exc}"
        ) from exc
    if live_inventory != inventory:
        raise LuaCensusError(
            "installation does not match the supplied sealed inventory"
        )
    content_root_value = live_inventory.get("content_root")
    if type(content_root_value) is not str or not content_root_value:
        raise LuaCensusError("inventory.content_root must be text")
    relative = PurePosixPath(content_root_value)
    if relative.is_absolute() or ".." in relative.parts or "\\" in content_root_value:
        raise LuaCensusError("inventory.content_root is not canonical")
    root = install_root.expanduser().resolve()
    content_root = root.joinpath(*relative.parts)
    if not content_root.resolve().is_relative_to(root):
        raise LuaCensusError("inventory content root escapes the installation")
    return content_root, _build_identity(live_inventory)


def _stable_file_sha256(path: Path, label: str) -> tuple[int, str]:
    if path.is_symlink() or not path.is_file():
        raise LuaCensusError(f"{label} is not a regular non-symlink file")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        handle_before = os.fstat(stream.fileno())
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
        if any(getattr(before, field) != getattr(handle_before, field) for field in fields):
            raise LuaCensusError(f"{label} changed while being opened")
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
        handle_after = os.fstat(stream.fileno())
        if any(
            getattr(handle_before, field) != getattr(handle_after, field)
            for field in fields
        ):
            raise LuaCensusError(f"{label} changed while being read")
    after = path.stat()
    if any(getattr(handle_after, field) != getattr(after, field) for field in fields):
        raise LuaCensusError(f"{label} changed after being read")
    return after.st_size, digest.hexdigest()


def _lupa_compiler() -> tuple[Callable[[bytes, str], bytes], dict[str, Any]]:
    try:
        import lupa
        from lupa import lua51
    except ImportError as exc:  # pragma: no cover - optional local dependency
        raise LuaCensusError("Lua census requires the optional lupa.lua51 package") from exc
    try:
        runtime = lua51.LuaRuntime(
            encoding=None,
            register_eval=False,
            register_builtins=False,
        )
        version = runtime.eval(b"_VERSION")
        dump_function = runtime.eval(b"string.dump")
    except Exception as exc:  # pragma: no cover - environment failure
        raise LuaCensusError(f"could not initialize Lua 5.1 compiler: {exc}") from exc
    if runtime.lua_version != (5, 1) or version != b"Lua 5.1":
        raise LuaCensusError("compiler backend is not Lua 5.1")
    def compile_source(source: bytes, path: str) -> bytes:
        chunk_name = ("@" + path).encode("utf-8")
        try:
            function = runtime.compile(source, name=chunk_name)
            dumped = dump_function(function)
        except Exception as exc:
            raise LuaCensusError(
                f"Lua 5.1 compilation failed for {path}: {exc}"
            ) from exc
        if not isinstance(dumped, bytes):
            raise LuaCensusError(
                f"Lua compiler returned non-bytecode output for {path}"
            )
        return dumped

    return compile_source, {
        "backend": "lupa.lua51",
        "lupa_version": str(lupa.__version__),
        "runtime_version": "Lua 5.1",
        "game_chunks_executed": False,
    }


def _exact_dll_compiler(
    install_root: Path,
    inventory: Mapping[str, Any],
    rustc: Path,
) -> tuple[Callable[[bytes, str], bytes], dict[str, Any]]:
    if os.name != "nt":
        raise LuaCensusError("exact Lua DLL compilation requires Windows")
    libraries = inventory.get("native_libraries")
    if not isinstance(libraries, list):
        raise LuaCensusError("inventory.native_libraries must be an array")
    matches = [
        library
        for library in libraries
        if isinstance(library, Mapping) and library.get("path") == "lua5.1.dll"
    ]
    if len(matches) != 1:
        raise LuaCensusError("inventory must contain exactly one lua5.1.dll")
    library = matches[0]
    dll = install_root.expanduser().resolve() / "lua5.1.dll"
    dll_size, dll_sha256 = _stable_file_sha256(dll, "lua5.1.dll")
    if (
        library.get("size") != dll_size
        or library.get("sha256") != dll_sha256
        or library.get("architecture") != "x86"
    ):
        raise LuaCensusError("lua5.1.dll does not match the sealed inventory")
    helper_source = Path(__file__).resolve().parents[2] / "scripts/windows_lua51_dump.rs"
    source_size, source_sha256 = _stable_file_sha256(
        helper_source,
        "compiler helper source",
    )
    if source_size < 1:
        raise LuaCensusError("compiler helper source is empty")

    rustc_command = shutil.which(str(rustc))
    if rustc_command is None:
        explicit_rustc = rustc.expanduser()
        if not explicit_rustc.is_file():
            raise LuaCensusError(f"could not find rustc executable: {rustc}")
        rustc_path = explicit_rustc.resolve()
    else:
        rustc_path = Path(rustc_command).resolve()
    rustc_size, rustc_sha256 = _stable_file_sha256(rustc_path, "rustc")
    creationflags = subprocess.CREATE_NO_WINDOW
    try:
        version_result = subprocess.run(
            [str(rustc_path), "--version", "--verbose"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
            creationflags=creationflags,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise LuaCensusError(f"could not identify rustc: {exc}") from exc
    if (
        version_result.returncode != 0
        or not version_result.stdout
        or len(version_result.stdout) > 64 * 1024
        or len(version_result.stderr) > 64 * 1024
    ):
        raise LuaCensusError("rustc version attestation failed")
    try:
        rustc_version = version_result.stdout.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise LuaCensusError("rustc version output is not UTF-8") from exc

    helper_workspace = tempfile.TemporaryDirectory(prefix="itb-lua51-helper-")
    helper = Path(helper_workspace.name) / "windows_lua51_dump.exe"
    repository_root = Path(__file__).resolve().parents[2]
    build_arguments = [
        "--edition",
        "2021",
        "--target",
        "i686-pc-windows-msvc",
        "-C",
        "opt-level=2",
        "-C",
        "codegen-units=1",
        "-C",
        "debuginfo=0",
        "-C",
        "strip=symbols",
        "-C",
        "panic=abort",
        "-C",
        "link-arg=/Brepro",
        f"--remap-path-prefix={repository_root}=.",
    ]
    try:
        build_result = subprocess.run(
            [
                str(rustc_path),
                *build_arguments,
                str(helper_source),
                "-o",
                str(helper),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=120,
            creationflags=creationflags,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        helper_workspace.cleanup()
        raise LuaCensusError(f"could not build exact Lua compiler helper: {exc}") from exc
    if build_result.returncode != 0:
        message = build_result.stderr[:8_192].decode(
            "utf-8",
            errors="replace",
        ).strip()
        helper_workspace.cleanup()
        raise LuaCensusError(
            f"could not build exact Lua compiler helper: {message}"
        )
    source_size_after, source_sha256_after = _stable_file_sha256(
        helper_source,
        "compiler helper source",
    )
    rustc_size_after, rustc_sha256_after = _stable_file_sha256(rustc_path, "rustc")
    if (source_size_after, source_sha256_after) != (source_size, source_sha256):
        helper_workspace.cleanup()
        raise LuaCensusError("compiler helper source changed while being built")
    if (rustc_size_after, rustc_sha256_after) != (rustc_size, rustc_sha256):
        helper_workspace.cleanup()
        raise LuaCensusError("rustc changed while building the compiler helper")
    try:
        helper_format = inspect_executable_format(helper)
    except (InventoryError, OSError) as exc:
        helper_workspace.cleanup()
        raise LuaCensusError(f"invalid compiler helper executable: {exc}") from exc
    if helper_format != {"format": "pe", "architecture": "x86"}:
        helper_workspace.cleanup()
        raise LuaCensusError("compiler helper is not a 32-bit x86 PE")
    helper_size, helper_sha256 = _stable_file_sha256(helper, "compiler helper")
    if helper_size < 1:
        helper_workspace.cleanup()
        raise LuaCensusError("compiler helper is empty")

    def compile_source(
        source: bytes,
        path: str,
        _workspace: tempfile.TemporaryDirectory[str] = helper_workspace,
    ) -> bytes:
        try:
            result = subprocess.run(
                [
                    str(helper),
                    "--dll",
                    str(dll),
                    "--chunk-name",
                    "@" + path,
                ],
                input=source,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
                creationflags=creationflags,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise LuaCensusError(
                f"exact Lua compiler helper failed for {path}: {exc}"
            ) from exc
        if result.returncode != 0:
            message = result.stderr[:4096].decode("utf-8", errors="replace").strip()
            raise LuaCensusError(
                f"exact Lua 5.1 compilation failed for {path}: {message}"
            )
        if not result.stdout:
            raise LuaCensusError(f"exact Lua compiler returned no bytecode for {path}")
        if len(result.stdout) > MAX_LUA_SOURCE_BYTES * 8:
            raise LuaCensusError(
                f"exact Lua compiler output exceeds the bytecode limit: {path}"
            )
        return result.stdout

    return compile_source, {
        "backend": "exact_inventory_lua51_dll",
        "runtime_version": "Lua 5.1",
        "dll": {
            "path": "lua5.1.dll",
            "size": dll_size,
            "sha256": dll_sha256,
            "architecture": "x86",
        },
        "helper_protocol": "windows_lua51_dump_v1",
        "helper_build": {
            "source_path": "scripts/windows_lua51_dump.rs",
            "source_size": source_size,
            "source_sha256": source_sha256,
            "target": "i686-pc-windows-msvc",
            "arguments": [
                "--edition=2021",
                "-C opt-level=2",
                "-C codegen-units=1",
                "-C debuginfo=0",
                "-C strip=symbols",
                "-C panic=abort",
                "-C link-arg=/Brepro",
                "--remap-path-prefix=<repository>=.",
            ],
            "rustc": {
                "size": rustc_size,
                "sha256": rustc_sha256,
                "version_verbose": rustc_version,
            },
        },
        "helper_binary": {
            "size": helper_size,
            "sha256": helper_sha256,
            "format": "pe",
            "architecture": "x86",
        },
        "game_chunks_executed": False,
    }


def _compile_chunk(
    compile_source: Callable[[bytes, str], bytes],
    source: bytes,
    path: str,
) -> Lua51Chunk:
    if len(source) > MAX_LUA_SOURCE_BYTES:
        raise LuaCensusError(f"Lua source exceeds the analysis size limit: {path}")
    try:
        dumped = compile_source(source, path)
        chunk = parse_lua51_chunk(dumped)
    except Lua51BytecodeError as exc:
        raise LuaCensusError(f"invalid compiler output for {path}: {exc}") from exc
    expected_source = ("@" + path).encode("utf-8")
    for prototype in flatten_prototypes(chunk.root):
        if prototype.source != expected_source:
            raise LuaCensusError(
                f"compiler source identity mismatch in {path} "
                f"prototype {prototype.prototype_path}"
            )
    return chunk


def _span_tree(text: str, spans: list[tuple[int, int]], path: str) -> _FunctionSpan:
    root = _FunctionSpan(-1, len(text) + 1)
    stack = [root]
    for start, end in spans:
        while stack and not (
            stack[-1].start < start and end <= stack[-1].end
        ):
            stack.pop()
        if not stack or start < 0 or end <= start or end > len(text):
            raise LuaCensusError(f"invalid lexical function nesting in {path}")
        node = _FunctionSpan(start, end)
        stack[-1].children.append(node)
        stack.append(node)
    return root


def _pair_spans(
    path: str,
    text: str,
    span: _FunctionSpan,
    prototype: Lua51Prototype,
    paired: dict[str, _FunctionSpan],
) -> None:
    if len(span.children) != len(prototype.children):
        raise LuaCensusError(
            f"compiled/lexical function-tree mismatch in {path} "
            f"at prototype {prototype.prototype_path}"
        )
    for child_span, child_prototype in zip(span.children, prototype.children):
        start_line = source_position(text, child_span.start)[0]
        end_line = source_position(text, child_span.end)[0]
        if (start_line, end_line) != (
            child_prototype.line_defined,
            child_prototype.last_line_defined,
        ):
            raise LuaCensusError(
                f"compiled/lexical function-line mismatch in {path} "
                f"at prototype {child_prototype.prototype_path}"
            )
        paired[child_prototype.prototype_path] = child_span
        _pair_spans(path, text, child_span, child_prototype, paired)


def _char_to_byte_offsets(text: str) -> list[int]:
    offsets = [0]
    cursor = 0
    for character in text:
        cursor += len(character.encode("utf-8"))
        offsets.append(cursor)
    return offsets


def _long_bracket_open(text: str, index: int) -> tuple[str, int] | None:
    if index >= len(text) or text[index] != "[":
        return None
    cursor = index + 1
    while cursor < len(text) and text[cursor] == "=":
        cursor += 1
    if cursor >= len(text) or text[cursor] != "[":
        return None
    equals = text[index + 1 : cursor]
    return f"]{equals}]", cursor + 1


def _blank_non_newlines(masked: list[str], start: int, end: int) -> None:
    for index in range(start, end):
        if masked[index] not in "\r\n":
            masked[index] = " "


def _mask_lua_comments(text: str) -> str:
    """Blank Lua comments while retaining string literals and exact offsets."""
    masked = list(text)
    index = 0
    while index < len(text):
        if text.startswith("--", index):
            long_open = _long_bracket_open(text, index + 2)
            if long_open:
                delimiter, body_start = long_open
                close = text.find(delimiter, body_start)
                if close < 0:
                    raise LuaCensusError("unterminated Lua long comment")
                end = close + len(delimiter)
            else:
                newline = text.find("\n", index + 2)
                end = len(text) if newline < 0 else newline
            _blank_non_newlines(masked, index, end)
            index = end
            continue
        if text[index] in {"'", '"'}:
            quote = text[index]
            cursor = index + 1
            while cursor < len(text):
                if text[cursor] == "\\":
                    cursor += 2
                    continue
                if text[cursor] == quote:
                    cursor += 1
                    break
                cursor += 1
            else:
                raise LuaCensusError("unterminated Lua short string")
            index = cursor
            continue
        long_open = _long_bracket_open(text, index)
        if long_open:
            delimiter, body_start = long_open
            close = text.find(delimiter, body_start)
            if close < 0:
                raise LuaCensusError("unterminated Lua long string")
            index = close + len(delimiter)
            continue
        index += 1
    return "".join(masked)


def _short_string_at(text: str, index: int) -> tuple[int, str | None]:
    if index >= len(text) or text[index] not in {"'", '"'}:
        raise LuaCensusError("expected Lua short string")
    quote = text[index]
    cursor = index + 1
    escaped = False
    while cursor < len(text):
        if text[cursor] == "\\":
            escaped = True
            cursor += 2
            continue
        if text[cursor] == quote:
            value = None if escaped else text[index + 1 : cursor]
            return cursor + 1, value
        cursor += 1
    raise LuaCensusError("unterminated Lua short string")


def _literal_dofile_sites(
    text: str,
    masked: str,
    path: str,
) -> list[dict[str, Any]]:
    sites = []
    for match in _DOFILE_PREFIX_RE.finditer(masked):
        cursor = match.end()
        while cursor < len(text) and text[cursor] in " \t\r\n":
            cursor += 1
        if cursor >= len(text) or text[cursor] not in {"'", '"'}:
            continue
        literal_end, target = _short_string_at(text, cursor)
        cursor = literal_end
        while cursor < len(text) and text[cursor] in " \t\r\n":
            cursor += 1
        if (
            target is None
            or not _LUA_PATH_VALUE_RE.fullmatch(target)
            or cursor >= len(masked)
            or masked[cursor] != ")"
        ):
            continue
        line, column = source_position(text, match.start())
        sites.append(
            {
                "source_path": path,
                "line": line,
                "column": column,
                "target_path": target,
            }
        )
    return sites


def _get_scripts_targets(
    text: str,
    path: str,
    span_start: int,
    span_end: int,
    prototype: Lua51Prototype,
) -> list[dict[str, Any]]:
    comments_masked = _mask_lua_comments(text)
    header = re.compile(
        r"function[ \t\r\n]+GetScripts[ \t\r\n]*"
        r"\([ \t\r\n]*\)[ \t\r\n]*return[ \t\r\n]*\{"
    ).match(comments_masked, span_start, span_end)
    if header is None:
        raise LuaCensusError("GetScripts is not a direct returned-table declaration")
    cursor = header.end()
    literals: list[tuple[int, int, str]] = []
    while True:
        while cursor < span_end and comments_masked[cursor] in " \t\r\n":
            cursor += 1
        if cursor >= span_end:
            raise LuaCensusError("GetScripts returned table is unterminated")
        if comments_masked[cursor] == "}":
            cursor += 1
            break
        if comments_masked[cursor] not in {"'", '"'}:
            raise LuaCensusError(
                "GetScripts returned table contains a non-literal entry"
            )
        literal_start = cursor
        literal_end, target = _short_string_at(text, cursor)
        if target is None or not _LUA_PATH_VALUE_RE.fullmatch(target):
            raise LuaCensusError(
                "GetScripts returned table contains a non-canonical Lua path"
            )
        literals.append((literal_start, literal_end, target))
        cursor = literal_end
        while cursor < span_end and comments_masked[cursor] in " \t\r\n":
            cursor += 1
        if cursor < span_end and comments_masked[cursor] == ",":
            cursor += 1
            continue
        if cursor >= span_end or comments_masked[cursor] != "}":
            raise LuaCensusError(
                "GetScripts returned table entries must be comma-separated"
            )

    while cursor < span_end and comments_masked[cursor] in " \t\r\n":
        cursor += 1
    if comments_masked[cursor:span_end] != "end":
        raise LuaCensusError(
            "GetScripts contains code outside its direct returned table"
        )
    source_targets = [literal[2] for literal in literals]
    compiled_targets: list[str] = []
    for constant in prototype.string_constants:
        if constant is None:
            continue
        try:
            value = constant.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if _LUA_PATH_VALUE_RE.fullmatch(value):
            compiled_targets.append(value)
    if Counter(source_targets) != Counter(compiled_targets):
        raise LuaCensusError(
            "GetScripts source literals do not match its compiled constant table"
        )
    targets = []
    for sequence, (literal_start, _literal_end, target) in enumerate(
        literals,
        start=1,
    ):
        line, column = source_position(text, literal_start + 1)
        targets.append(
            {
                "source_path": path,
                "source_symbol": "GetScripts",
                "line": line,
                "column": column,
                "sequence": sequence,
                "target_path": target,
            }
        )
    return targets


def _classify_function(
    text: str,
    masked: str,
    brace_depths: list[int],
    span: _FunctionSpan,
) -> dict[str, Any]:
    explicit = _EXPLICIT_FUNCTION_RE.match(masked, span.start)
    symbol: str | None = None
    symbol_offset: int | None = None
    if explicit:
        symbol = explicit.group("name")
        symbol_offset = explicit.start("name")
        kind = (
            "local_function_declaration"
            if _LOCAL_BEFORE_RE.search(masked[: span.start])
            else "function_declaration"
        )
    else:
        prefix_start = max(0, span.start - 2_048)
        assignment = _ASSIGNMENT_BEFORE_RE.search(masked[prefix_start : span.start])
        if assignment:
            symbol = assignment.group("name")
            symbol_offset = prefix_start + assignment.start("name")
            if assignment.group("local"):
                kind = "local_function_assignment"
            elif brace_depths[symbol_offset] > 0:
                kind = "table_field_function"
            else:
                kind = "function_assignment"
        else:
            kind = "anonymous_function"

    start_line, start_column = source_position(text, span.start)
    end_line, end_column = source_position(text, span.end)
    result: dict[str, Any] = {
        "definition_kind": kind,
        "symbol": symbol,
        "line": start_line,
        "column": start_column,
        "end_line": end_line,
        "end_column": end_column,
    }
    if symbol_offset is None:
        result["symbol_line"] = None
        result["symbol_column"] = None
    else:
        result["symbol_line"], result["symbol_column"] = source_position(
            text,
            symbol_offset,
        )
    return result


def _optional_identifier_constant(
    prototype: Lua51Prototype,
    index: int | None,
) -> str | None:
    if index is None or index < 0 or index >= prototype.constant_count:
        return None
    raw = prototype.string_constants[index]
    if raw is None or not _IDENTIFIER_BYTES_RE.fullmatch(raw):
        return None
    return raw.decode("ascii")


def _instruction_metadata(prototype: Lua51Prototype) -> dict[str, Any]:
    opcodes: Counter[str] = Counter()
    global_reads: Counter[str] = Counter()
    global_writes: Counter[str] = Counter()
    member_reads: Counter[str] = Counter()
    member_writes: Counter[str] = Counter()
    method_lookups: Counter[str] = Counter()
    for instruction in prototype.instructions:
        opcode = instruction_opcode(instruction)
        name = OPCODE_NAMES[opcode]
        opcodes[name] += 1
        if name in {"GETGLOBAL", "SETGLOBAL"}:
            try:
                symbol = identifier_constant(
                    prototype,
                    instruction_bx(instruction),
                    label=name,
                )
            except Lua51BytecodeError as exc:
                raise LuaCensusError(str(exc)) from exc
            (global_reads if name == "GETGLOBAL" else global_writes)[symbol] += 1
        elif name == "GETTABLE":
            symbol = _optional_identifier_constant(
                prototype,
                rk_constant_index(instruction_c(instruction)),
            )
            if symbol is not None:
                member_reads[symbol] += 1
        elif name == "SETTABLE":
            symbol = _optional_identifier_constant(
                prototype,
                rk_constant_index(instruction_b(instruction)),
            )
            if symbol is not None:
                member_writes[symbol] += 1
        elif name == "SELF":
            symbol = _optional_identifier_constant(
                prototype,
                rk_constant_index(instruction_c(instruction)),
            )
            if symbol is not None:
                method_lookups[symbol] += 1

    def normalized(counter: Counter[str], key: str = "name") -> list[dict[str, Any]]:
        return [
            {key: name, "occurrences": counter[name]}
            for name in sorted(counter)
        ]

    return {
        "opcode_counts": [
            {"opcode": name, "count": opcodes[name]}
            for name in OPCODE_NAMES
            if opcodes[name]
        ],
        "global_reads": normalized(global_reads),
        "global_writes": normalized(global_writes),
        "member_reads": normalized(member_reads),
        "member_writes": normalized(member_writes),
        "method_lookups": normalized(method_lookups),
    }


def _inventory_entries(inventory: Mapping[str, Any]) -> list[dict[str, Any]]:
    content = _mapping(inventory.get("content"), "inventory.content")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for collection in ("scripts", "maps"):
        manifest = _mapping(
            content.get(collection),
            f"inventory.content.{collection}",
        )
        entries = manifest.get("files")
        if not isinstance(entries, list):
            raise LuaCensusError(
                f"inventory.content.{collection}.files must be an array"
            )
        for index, value in enumerate(entries):
            entry = _mapping(value, f"inventory {collection} entry {index}")
            path = entry.get("path")
            size = entry.get("size")
            sha256 = entry.get("sha256")
            if (
                type(path) is not str
                or not path.startswith(f"{collection}/")
                or "\\" in path
                or PurePosixPath(path).as_posix() != path
                or "." in PurePosixPath(path).parts
                or ".." in PurePosixPath(path).parts
                or type(size) is not int
                or size < 0
                or type(sha256) is not str
                or not _SHA256_RE.fullmatch(sha256)
            ):
                raise LuaCensusError(
                    f"inventory {collection} entry {index} is malformed"
                )
            if path in seen:
                raise LuaCensusError(f"duplicate inventory content path: {path}")
            seen.add(path)
            result.append({**entry, "collection": collection})
    return sorted(result, key=lambda entry: str(entry["path"]))


def _file_disposition(path: str, collection: str) -> str:
    if path in LOCAL_OVERLAY_PATHS:
        return (
            "owner_lua_overlay_excluded"
            if path.endswith(".lua")
            else "owner_overlay_backup_excluded"
        )
    if collection == "scripts" and path.endswith(".lua"):
        return "accepted_game_lua_analyzed"
    if collection == "maps" and path == "maps/maphelper.lua":
        return "accepted_map_bootstrap_lua_analyzed"
    if collection == "maps" and path.endswith(".map"):
        return "accepted_map_data_lua_analyzed"
    return "non_lua_inventory_entry"


def _validate_callback_index(
    callback_index: Mapping[str, Any],
    build_identity: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    if callback_index.get("analysis_kind") != "lua_callback_provenance_index":
        raise LuaCensusError("callback index has the wrong analysis kind")
    callback_identity = _mapping(
        callback_index.get("build_identity"),
        "callback_index.build_identity",
    )
    for key in ("platform", "architecture", "build_id", "executable_sha256"):
        if callback_identity.get(key) != build_identity.get(key):
            raise LuaCensusError(f"callback index build identity mismatch: {key}")
    callbacks = callback_index.get("callbacks")
    if not isinstance(callbacks, list):
        raise LuaCensusError("callback_index.callbacks must be an array")
    return [
        _mapping(callback, f"callback_index.callbacks[{index}]")
        for index, callback in enumerate(callbacks)
    ]


def _build_static_load_graph(
    files: list[dict[str, Any]],
    get_scripts_sites: list[dict[str, Any]],
    dofile_sites: list[dict[str, Any]],
    dofile_global_occurrences: int,
) -> dict[str, Any]:
    file_by_path = {file["path"]: file for file in files}
    if len(file_by_path) != len(files):
        raise LuaCensusError("duplicate file while constructing load graph")
    required_bootstraps = {
        "scripts/scripts.lua": "accepted_game_lua_analyzed",
        "maps/maphelper.lua": "accepted_map_bootstrap_lua_analyzed",
    }
    for path, disposition in required_bootstraps.items():
        file = file_by_path.get(path)
        if file is None or file["disposition"] != disposition:
            raise LuaCensusError(f"required host bootstrap is absent: {path}")
    if not get_scripts_sites:
        raise LuaCensusError("compiled GetScripts declaration was not found")
    if len(dofile_sites) > dofile_global_occurrences:
        raise LuaCensusError(
            "literal dofile sites exceed compiled GETGLOBAL dofile occurrences"
        )

    raw_edges: list[dict[str, Any]] = []

    def append_edge(
        *,
        route_kind: str,
        proof_class: str,
        target_path: str,
        source_path: str | None,
        source_symbol: str | None,
        line: int | None,
        column: int | None,
        sequence: int | None,
    ) -> None:
        target = file_by_path.get(target_path)
        if target is None:
            target_status = "external_not_in_inventory"
            target_disposition = None
            target_sha256 = None
        elif target["disposition"] in _ANALYZED_DISPOSITIONS:
            target_status = "accepted_analyzed"
            target_disposition = target["disposition"]
            target_sha256 = target["sha256"]
        elif target["disposition"] == "owner_lua_overlay_excluded":
            target_status = "excluded_owner_overlay"
            target_disposition = target["disposition"]
            target_sha256 = target["sha256"]
        else:
            target_status = "inventory_entry_not_analyzed"
            target_disposition = target["disposition"]
            target_sha256 = target["sha256"]
        raw_edges.append(
            {
                "route_kind": route_kind,
                "proof_class": proof_class,
                "source_path": source_path,
                "source_symbol": source_symbol,
                "line": line,
                "column": column,
                "sequence": sequence,
                "target_path": target_path,
                "target_status": target_status,
                "target_disposition": target_disposition,
                "target_sha256": target_sha256,
            }
        )

    append_edge(
        route_kind="host_bootstrap",
        proof_class="host_bootstrap_assumption",
        source_path=None,
        source_symbol="host_runtime",
        line=None,
        column=None,
        sequence=1,
        target_path="scripts/scripts.lua",
    )
    append_edge(
        route_kind="host_bootstrap",
        proof_class="host_bootstrap_assumption",
        source_path=None,
        source_symbol="host_runtime",
        line=None,
        column=None,
        sequence=2,
        target_path="maps/maphelper.lua",
    )
    for site in get_scripts_sites:
        append_edge(
            route_kind="get_scripts_return_literal",
            proof_class="compiled_direct_return_literal_crosscheck",
            target_path=site["target_path"],
            source_path=site["source_path"],
            source_symbol=site["source_symbol"],
            line=site["line"],
            column=site["column"],
            sequence=site["sequence"],
        )
    for sequence, site in enumerate(
        sorted(
            dofile_sites,
            key=lambda item: (
                item["source_path"],
                item["line"],
                item["column"],
                item["target_path"],
            ),
        ),
        start=1,
    ):
        append_edge(
            route_kind="literal_dofile_site",
            proof_class="compiled_loader_and_literal_site_crosscheck",
            target_path=site["target_path"],
            source_path=site["source_path"],
            source_symbol=None,
            line=site["line"],
            column=site["column"],
            sequence=sequence,
        )
    map_files = sorted(
        (
            file
            for file in files
            if file["disposition"] == "accepted_map_data_lua_analyzed"
        ),
        key=lambda file: file["path"],
    )
    for sequence, file in enumerate(map_files, start=1):
        append_edge(
            route_kind="map_directory_discovery",
            proof_class="host_directory_discovery_assumption",
            target_path=file["path"],
            source_path=None,
            source_symbol="host_map_loader",
            line=None,
            column=None,
            sequence=sequence,
        )

    edges = []
    route_ids: dict[str, list[str]] = defaultdict(list)
    for index, edge in enumerate(raw_edges, start=1):
        normalized = {"id": f"load-{index:04d}", **edge}
        edges.append(normalized)
        if edge["target_path"] in file_by_path:
            route_ids[edge["target_path"]].append(normalized["id"])

    file_routes = []
    for file in files:
        disposition = file["disposition"]
        if disposition not in _ANALYZED_DISPOSITIONS and disposition != (
            "owner_lua_overlay_excluded"
        ):
            continue
        ids = route_ids[file["path"]]
        if disposition == "owner_lua_overlay_excluded":
            status = (
                "excluded_owner_overlay_declared"
                if ids
                else "excluded_owner_overlay_unrouted"
            )
        else:
            status = (
                "covered_by_static_load_model"
                if ids
                else "unrouted_in_static_load_model"
            )
        file_routes.append(
            {
                "path": file["path"],
                "disposition": disposition,
                "route_status": status,
                "route_ids": ids,
            }
        )

    accepted_routes = [
        route
        for route in file_routes
        if route["disposition"] in _ANALYZED_DISPOSITIONS
    ]
    target_counts = Counter(edge["target_path"] for edge in edges)
    return {
        "method": {
            "host_bootstrap": (
                "scripts/scripts.lua and maps/maphelper.lua are modeled as host "
                "entry points; this is an explicit loader assumption, not a "
                "recovered native registration proof"
            ),
            "get_scripts": (
                "GetScripts must consist only of a direct returned table of "
                "canonical literal paths, which must match that compiled "
                "prototype's path-valued string constants; host invocation is "
                "not proved"
            ),
            "literal_dofile": (
                "only syntactic dofile(GetWorkingDir()..literal_path) sites are "
                "resolved; the extracted site count cannot exceed compiled "
                "dofile reads, and reachability is not claimed"
            ),
            "map_discovery": (
                "sealed maps/*.map entries are modeled as directory-discovered "
                "host inputs, explicitly as an assumption"
            ),
        },
        "edges": edges,
        "file_routes": file_routes,
        "summary": {
            "modeled_edges": len(edges),
            "compiler_source_derived_edges": (
                len(get_scripts_sites) + len(dofile_sites)
            ),
            "assumption_edges": 2 + len(map_files),
            "host_bootstrap_assumptions": 2,
            "get_scripts_return_literal_edges": len(get_scripts_sites),
            "literal_dofile_site_edges": len(dofile_sites),
            "compiled_dofile_global_occurrences": dofile_global_occurrences,
            "unresolved_dofile_global_occurrences": (
                dofile_global_occurrences - len(dofile_sites)
            ),
            "map_directory_discovery_assumptions": len(map_files),
            "accepted_analyzed_files": len(accepted_routes),
            "accepted_covered_by_load_model": sum(
                route["route_status"] == "covered_by_static_load_model"
                for route in accepted_routes
            ),
            "accepted_unrouted_in_load_model": sum(
                route["route_status"] == "unrouted_in_static_load_model"
                for route in accepted_routes
            ),
            "external_targets": len(
                {
                    edge["target_path"]
                    for edge in edges
                    if edge["target_status"] == "external_not_in_inventory"
                }
            ),
            "declared_excluded_owner_overlays": sum(
                edge["target_status"] == "excluded_owner_overlay"
                for edge in edges
            ),
            "duplicate_target_edges": sum(
                max(0, count - 1) for count in target_counts.values()
            ),
        },
    }


def build_lua_census(
    install_root: Path,
    *,
    inventory: Mapping[str, Any],
    callback_index: Mapping[str, Any],
    rustc: Path | None = None,
) -> dict[str, Any]:
    """Compile and inventory every accepted Lua source in one sealed install."""
    if not isinstance(inventory, Mapping):
        raise LuaCensusError("inventory must be an object")
    if not isinstance(callback_index, Mapping):
        raise LuaCensusError("callback index must be an object")
    content_root, build_identity = _attest_installation(install_root, inventory)
    callbacks = _validate_callback_index(callback_index, build_identity)
    if rustc is None:
        compile_source, compiler = _lupa_compiler()
    else:
        compile_source, compiler = _exact_dll_compiler(
            install_root,
            inventory,
            rustc,
        )

    files: list[dict[str, Any]] = []
    functions: list[dict[str, Any]] = []
    member_lexical: Counter[tuple[str, str, str]] = Counter()
    member_paths: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    get_scripts_sites: list[dict[str, Any]] = []
    dofile_sites: list[dict[str, Any]] = []
    dofile_global_occurrences = 0
    observed_header: Mapping[str, Any] | None = None

    for entry in _inventory_entries(inventory):
        path = str(entry["path"])
        collection = str(entry["collection"])
        disposition = _file_disposition(path, collection)
        file_record: dict[str, Any] = {
            "path": path,
            "collection": collection,
            "size": entry["size"],
            "sha256": entry["sha256"],
            "extension": PurePosixPath(path).suffix.casefold(),
            "disposition": disposition,
        }
        if disposition not in _ANALYZED_DISPOSITIONS:
            file_record.update(
                {
                    "compile_status": "not_applicable",
                    "compiled_chunks": 0,
                    "function_prototypes": 0,
                    "total_prototypes": 0,
                    "instruction_count": 0,
                    "named_functions": 0,
                    "anonymous_functions": 0,
                    "global_read_occurrences": 0,
                    "global_write_occurrences": 0,
                    "global_table_index_sites": 0,
                    "global_table_write_sites": 0,
                }
            )
            files.append(file_record)
            continue

        relative = PurePosixPath(path)
        try:
            text = read_exact_inventory_file(
                content_root,
                relative,
                expected_size=entry["size"],
                expected_sha256=entry["sha256"],
            )
            masked = mask_lua_opaque(text)
            spans = lua_function_spans(masked)
            brace_depths = lua_brace_depths(masked)
        except WeaponCoverageError as exc:
            raise LuaCensusError(f"{path}: {exc}") from exc
        source = text.encode("utf-8")
        if len(source) != entry["size"]:
            raise LuaCensusError(f"UTF-8 round trip changed source bytes: {path}")
        chunk = _compile_chunk(compile_source, source, path)
        normalized_header = chunk.header.normalized()
        if observed_header is None:
            observed_header = normalized_header
        elif normalized_header != observed_header:
            raise LuaCensusError("Lua compiler emitted inconsistent chunk headers")

        span_root = _span_tree(text, spans, path)
        paired: dict[str, _FunctionSpan] = {}
        _pair_spans(path, text, span_root, chunk.root, paired)
        prototypes = flatten_prototypes(chunk.root)
        if len(paired) + 1 != len(prototypes):
            raise LuaCensusError(f"unpaired compiled prototype in {path}")
        byte_offsets = _char_to_byte_offsets(text)
        file_functions: list[dict[str, Any]] = []
        for prototype in prototypes:
            if prototype.prototype_path == "0":
                span_start = 0
                span_end = len(text)
                start_line, start_column = 1, 1
                end_line, end_column = source_position(text, len(text))
                lexical = {
                    "definition_kind": "chunk",
                    "symbol": None,
                    "line": start_line,
                    "column": start_column,
                    "end_line": end_line,
                    "end_column": end_column,
                    "symbol_line": None,
                    "symbol_column": None,
                }
            else:
                span = paired[prototype.prototype_path]
                span_start = span.start
                span_end = span.end
                lexical = _classify_function(text, masked, brace_depths, span)
            source_start = byte_offsets[span_start]
            source_end = byte_offsets[span_end]
            instruction_metadata = _instruction_metadata(prototype)
            function_record = {
                "source_path": path,
                "source_sha256": entry["sha256"],
                "prototype_path": prototype.prototype_path,
                "parent_prototype_path": (
                    None
                    if prototype.prototype_path == "0"
                    else prototype.prototype_path.rsplit("/", 1)[0]
                ),
                "scope": (
                    "chunk"
                    if prototype.prototype_path == "0"
                    else "top_level"
                    if prototype.prototype_path.count("/") == 1
                    else "nested"
                ),
                **lexical,
                "source_span_bytes": source_end - source_start,
                "source_span_sha256": hashlib.sha256(
                    source[source_start:source_end]
                ).hexdigest(),
                "serialized_prototype_size": prototype.serialized_size,
                "serialized_prototype_sha256": prototype.serialized_sha256,
                "parameter_count": prototype.parameter_count,
                "vararg_flags": prototype.vararg_flags,
                "upvalue_count": prototype.upvalue_count,
                "max_stack_size": prototype.max_stack_size,
                "instruction_count": len(prototype.instructions),
                "constant_count": prototype.constant_count,
                "nested_prototype_count": len(prototype.children),
                "line_info_count": len(prototype.line_info),
                "local_debug_count": len(prototype.locals),
                "upvalue_name_count": len(prototype.upvalue_names),
                **instruction_metadata,
            }
            file_functions.append(function_record)
            functions.append(function_record)
            if path == "scripts/scripts.lua" and lexical["symbol"] == "GetScripts":
                if get_scripts_sites:
                    raise LuaCensusError("multiple GetScripts declarations found")
                get_scripts_sites = _get_scripts_targets(
                    text,
                    path,
                    span_start,
                    span_end,
                    prototype,
                )

        literal_sites = _literal_dofile_sites(text, masked, path)
        compiled_dofile_reads = sum(
            access["occurrences"]
            for function in file_functions
            for access in function["global_reads"]
            if access["name"] == "dofile"
        )
        if len(literal_sites) > compiled_dofile_reads:
            raise LuaCensusError(
                f"literal dofile sites exceed compiled reads in {path}"
            )
        dofile_sites.extend(literal_sites)
        dofile_global_occurrences += compiled_dofile_reads

        for match in _MEMBER_RE.finditer(masked):
            key = (
                match.group("root"),
                match.group("member"),
                match.group("separator"),
            )
            member_lexical[key] += 1
            member_paths[key].add(path)

        file_record.update(
            {
                "compile_status": "compiled_not_executed",
                "compiled_chunks": 1,
                "function_prototypes": len(prototypes) - 1,
                "total_prototypes": len(prototypes),
                "instruction_count": sum(
                    function["instruction_count"] for function in file_functions
                ),
                "named_functions": sum(
                    function["symbol"] is not None
                    for function in file_functions
                    if function["definition_kind"] != "chunk"
                ),
                "anonymous_functions": sum(
                    function["symbol"] is None
                    for function in file_functions
                    if function["definition_kind"] != "chunk"
                ),
                "global_read_occurrences": sum(
                    access["occurrences"]
                    for function in file_functions
                    for access in function["global_reads"]
                ),
                "global_write_occurrences": sum(
                    access["occurrences"]
                    for function in file_functions
                    for access in function["global_writes"]
                ),
                "global_table_index_sites": len(
                    _GLOBAL_TABLE_INDEX_RE.findall(masked)
                ),
                "global_table_write_sites": len(
                    _GLOBAL_TABLE_WRITE_RE.findall(masked)
                ),
            }
        )
        files.append(file_record)

    if observed_header is None:
        raise LuaCensusError("no accepted Lua sources were compiled")
    compiler["chunk_header"] = dict(observed_header)

    for index, function in enumerate(functions, start=1):
        function["id"] = f"lua-{index:06d}"
    function_ids = {
        (function["source_path"], function["prototype_path"]): function["id"]
        for function in functions
    }
    for function in functions:
        parent_path = function.pop("parent_prototype_path")
        function["parent_id"] = (
            None
            if parent_path is None
            else function_ids[(function["source_path"], parent_path)]
        )

    global_counts: dict[str, Counter[str]] = defaultdict(Counter)
    global_readers: dict[str, set[str]] = defaultdict(set)
    global_writers: dict[str, set[str]] = defaultdict(set)
    global_files: dict[str, set[str]] = defaultdict(set)
    for function in functions:
        for field_name, occurrence_key, function_set in (
            ("global_reads", "reads", global_readers),
            ("global_writes", "writes", global_writers),
        ):
            for access in function[field_name]:
                name = access["name"]
                global_counts[name][occurrence_key] += access["occurrences"]
                function_set[name].add(function["id"])
                global_files[name].add(function["source_path"])
    globals_ = []
    for name in sorted(global_counts):
        counts = global_counts[name]
        classification = (
            "corpus_environment_defined"
            if counts["writes"]
            else "lua51_standard_or_library"
            if name in _STANDARD_GLOBALS
            else "unresolved_host_environment_candidate"
        )
        globals_.append(
            {
                "name": name,
                "classification": classification,
                "read_occurrences": counts["reads"],
                "write_occurrences": counts["writes"],
                "reader_functions": len(global_readers[name]),
                "writer_functions": len(global_writers[name]),
                "source_files": sorted(global_files[name]),
            }
        )
    global_classification = {
        item["name"]: item["classification"] for item in globals_
    }
    host_member_candidates = [
        {
            "root": root,
            "member": member,
            "separator": separator,
            "occurrences": member_lexical[(root, member, separator)],
            "source_files": sorted(member_paths[(root, member, separator)]),
            "classification": "unresolved_host_global_member_candidate",
        }
        for root, member, separator in sorted(member_lexical)
        if global_classification.get(root)
        == "unresolved_host_environment_candidate"
    ]
    load_graph = _build_static_load_graph(
        files,
        get_scripts_sites,
        dofile_sites,
        dofile_global_occurrences,
    )

    named_keys = {
        (
            function["source_path"],
            function["source_sha256"],
            function["symbol_line"],
            function["symbol"],
        )
        for function in functions
        if function["symbol"] is not None
    }
    missing_callbacks = []
    for index, callback in enumerate(callbacks):
        key = (
            callback.get("source_path"),
            callback.get("source_sha256"),
            callback.get("line"),
            callback.get("symbol"),
        )
        if key not in named_keys:
            missing_callbacks.append(index)
    if missing_callbacks:
        raise LuaCensusError(
            "callback index definitions are missing from the compiled census: "
            + ", ".join(str(index) for index in missing_callbacks[:20])
        )

    dispositions = Counter(file["disposition"] for file in files)
    definition_kinds = Counter(
        function["definition_kind"]
        for function in functions
        if function["definition_kind"] != "chunk"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": build_identity,
        "inventory": {
            "label": inventory.get("label"),
            "canonical_sha256": _canonical_sha256(inventory),
            "content_entries": len(files),
        },
        "compiler": compiler,
        "method": _METHOD,
        "files": files,
        "functions": functions,
        "globals": globals_,
        "host_member_candidates": host_member_candidates,
        "load_graph": load_graph,
        "callback_crosscheck": {
            "analysis_kind": callback_index.get("analysis_kind"),
            "canonical_sha256": _canonical_sha256(callback_index),
            "definitions": len(callbacks),
            "matched_definitions": len(callbacks),
        },
        "summary": {
            "inventory_content_entries": len(files),
            "accepted_script_lua_files": dispositions[
                "accepted_game_lua_analyzed"
            ],
            "accepted_map_bootstrap_lua_files": dispositions[
                "accepted_map_bootstrap_lua_analyzed"
            ],
            "accepted_map_data_lua_chunks": dispositions[
                "accepted_map_data_lua_analyzed"
            ],
            "excluded_owner_lua_overlays": dispositions[
                "owner_lua_overlay_excluded"
            ],
            "excluded_owner_overlay_backups": dispositions[
                "owner_overlay_backup_excluded"
            ],
            "non_lua_inventory_entries": dispositions["non_lua_inventory_entry"],
            "compiled_chunks": sum(file["compiled_chunks"] for file in files),
            "function_prototypes": sum(
                file["function_prototypes"] for file in files
            ),
            "total_prototypes": len(functions),
            "named_functions": sum(
                function["symbol"] is not None
                for function in functions
                if function["definition_kind"] != "chunk"
            ),
            "anonymous_functions": sum(
                function["symbol"] is None
                for function in functions
                if function["definition_kind"] != "chunk"
            ),
            "definition_kinds": [
                {"kind": kind, "count": definition_kinds[kind]}
                for kind in sorted(definition_kinds)
            ],
            "instructions": sum(
                function["instruction_count"] for function in functions
            ),
            "global_identifiers": len(globals_),
            "corpus_defined_environment_identifiers": sum(
                item["classification"] == "corpus_environment_defined"
                for item in globals_
            ),
            "standard_library_globals": sum(
                item["classification"] == "lua51_standard_or_library"
                for item in globals_
            ),
            "unresolved_host_environment_candidates": sum(
                item["classification"]
                == "unresolved_host_environment_candidate"
                for item in globals_
            ),
            "loader_global_occurrences": sum(
                item["read_occurrences"]
                for item in globals_
                if item["name"] in _LOADER_GLOBALS
            ),
            "setfenv_global_occurrences": sum(
                item["read_occurrences"]
                for item in globals_
                if item["name"] == "setfenv"
            ),
            "global_table_index_sites": sum(
                file["global_table_index_sites"] for file in files
            ),
            "global_table_write_sites": sum(
                file["global_table_write_sites"] for file in files
            ),
            "host_member_candidates": len(host_member_candidates),
            "callback_definitions_crosschecked": len(callbacks),
            "modeled_load_edges": load_graph["summary"]["modeled_edges"],
            "compiler_source_derived_load_edges": load_graph["summary"][
                "compiler_source_derived_edges"
            ],
            "assumed_load_edges": load_graph["summary"]["assumption_edges"],
            "accepted_files_covered_by_load_model": load_graph["summary"][
                "accepted_covered_by_load_model"
            ],
            "accepted_files_unrouted_in_load_model": load_graph["summary"][
                "accepted_unrouted_in_load_model"
            ],
        },
    }


def validate_lua_census(
    install_root: Path,
    evidence: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
    callback_index: Mapping[str, Any],
    rustc: Path | None = None,
) -> dict[str, Any]:
    """Rebuild and exact-compare a normalized Lua census."""
    if not isinstance(evidence, Mapping):
        raise LuaCensusError("evidence must be an object")
    expected = build_lua_census(
        install_root,
        inventory=inventory,
        callback_index=callback_index,
        rustc=rustc,
    )
    if evidence != expected:
        raise LuaCensusError(
            "Lua census does not match the exact installation and inputs"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": expected["build_identity"],
        "evidence_sha256": _canonical_sha256(evidence),
        "summary": expected["summary"],
    }


def encode_lua_census(value: Mapping[str, Any]) -> str:
    """Encode census or verification output deterministically."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
