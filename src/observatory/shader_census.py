"""Build-keyed, source-free census of Into the Breach OpenGL shaders."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from src.observatory.content_inventory import (
    InventoryError,
    build_manifest,
    create_inventory,
)
from src.observatory.pe_anchor_map import PEAnchorError, _inventory_identity
from src.observatory.weapon_coverage import (
    WeaponCoverageError,
    read_exact_inventory_file,
)


SCHEMA_VERSION = 1
ANALYSIS_KIND = "itb_opengl_shader_interface_census"
VERIFICATION_KIND = "itb_opengl_shader_interface_census_verification"
SHADER_DIRECTORY = "shadersOGL"
MAX_SHADER_SOURCE_BYTES = 1024 * 1024
MAX_IDENTIFIER_CHARACTERS = 128
MAX_PREPROCESSOR_CONDITIONAL_DEPTH = 256
MAX_PREPROCESSOR_EXPRESSION_TOKENS = 4096
_ALLOWED_EXTENSIONS = {
    ".vs": "vertex_stage_hint",
    ".ps": "fragment_stage_hint",
    ".h": "shared_header_hint",
}
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_IDENTIFIER_TOKEN_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_NUMBER_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?![A-Za-z0-9_])"
)
_DECLARATION_RE = re.compile(
    r"\b(?P<storage>uniform|attribute|varying)\s+"
    r"(?:(?P<precision>lowp|mediump|highp)\s+)?"
    r"(?P<type>[A-Za-z_][A-Za-z0-9_]*)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*;"
)
_DECLARATION_KEYWORD_RE = re.compile(r"\b(?:uniform|attribute|varying)\b")
_MAIN_RE = re.compile(r"\bvoid\s+(?P<name>main)\s*\(\s*\)\s*\{")
_CALL_RE = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
_BUILTIN_RE = re.compile(r"\bgl_[A-Za-z_][A-Za-z0-9_]*\b")
_DIRECTIVE_RE = re.compile(
    r"^\s*#\s*(?P<directive>[A-Za-z_][A-Za-z0-9_]*)(?P<body>.*)$"
)
_CONDITION_TOKEN_RE = re.compile(
    r"defined\b|[A-Za-z_][A-Za-z0-9_]*|[0-9]+|&&|\|\||!|\(|\)"
)
_SUPPORTED_DIRECTIVES = frozenset(
    {"if", "ifdef", "ifndef", "elif", "else", "endif", "define", "undef"}
)
_CONTROL_CALL_NAMES = frozenset({"if", "for", "while", "switch"})


class ShaderCensusError(RuntimeError):
    """Raised when shader inputs or interface evidence are untrustworthy."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ShaderCensusError(f"{label} must be an object")
    return value


def _canonical_sha256(value: Any) -> str:
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
        raise ShaderCensusError(f"invalid inventory identity: {exc}") from exc


def _attest_installation(
    install_root: Path,
    inventory: Mapping[str, Any],
) -> tuple[Path, dict[str, Any]]:
    platform_name = inventory.get("platform")
    label = inventory.get("label")
    if type(platform_name) is not str or not platform_name:
        raise ShaderCensusError("inventory.platform must be text")
    if label is not None and type(label) is not str:
        raise ShaderCensusError("inventory.label must be text or null")
    try:
        live_inventory = create_inventory(
            install_root,
            platform_name=platform_name,
            label=label,
        )
    except (InventoryError, OSError, UnicodeError) as exc:
        raise ShaderCensusError(
            f"could not rebuild the installation inventory: {exc}"
        ) from exc
    if live_inventory != inventory:
        raise ShaderCensusError(
            "installation does not match the supplied sealed inventory"
        )
    content_root_value = live_inventory.get("content_root")
    if type(content_root_value) is not str or not content_root_value:
        raise ShaderCensusError("inventory.content_root must be text")
    relative = PurePosixPath(content_root_value)
    if relative.is_absolute() or ".." in relative.parts or "\\" in content_root_value:
        raise ShaderCensusError("inventory.content_root is not canonical")
    root = install_root.expanduser().resolve()
    content_root = root.joinpath(*relative.parts)
    if not content_root.resolve().is_relative_to(root):
        raise ShaderCensusError("inventory content root escapes the installation")
    return content_root, _build_identity(live_inventory)


def _shader_manifest(content_root: Path) -> dict[str, Any]:
    root = content_root / SHADER_DIRECTORY
    if root.is_symlink() or not root.is_dir():
        raise ShaderCensusError(
            f"{SHADER_DIRECTORY} must be a regular non-symlink directory"
        )
    for child in root.iterdir():
        if child.is_symlink() or not child.is_file():
            raise ShaderCensusError(
                f"{SHADER_DIRECTORY} must contain only direct regular files"
            )
    try:
        manifest = build_manifest(content_root, SHADER_DIRECTORY)
    except (InventoryError, OSError) as exc:
        raise ShaderCensusError(f"could not inventory shaders: {exc}") from exc
    values = manifest.get("files")
    if not isinstance(values, list) or not values:
        raise ShaderCensusError("shader manifest contains no files")
    for index, value in enumerate(values):
        entry = _mapping(value, f"shader manifest entry {index}")
        path = entry.get("path")
        size = entry.get("size")
        sha256 = entry.get("sha256")
        if type(path) is not str:
            raise ShaderCensusError(f"shader manifest entry {index} has no path")
        relative = PurePosixPath(path)
        if (
            len(relative.parts) != 2
            or relative.parts[0] != SHADER_DIRECTORY
            or relative.as_posix() != path
            or relative.suffix.casefold() not in _ALLOWED_EXTENSIONS
            or relative.suffix != relative.suffix.casefold()
            or not _IDENTIFIER_RE.fullmatch(relative.stem)
            or len(relative.stem) > MAX_IDENTIFIER_CHARACTERS
            or type(size) is not int
            or size < 0
            or type(sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", sha256)
        ):
            raise ShaderCensusError(f"shader manifest entry {index} is malformed")
        if size > MAX_SHADER_SOURCE_BYTES:
            raise ShaderCensusError(f"shader exceeds source size limit: {path}")
    return manifest


def _require_identifier(value: str, label: str) -> str:
    if (
        len(value) > MAX_IDENTIFIER_CHARACTERS
        or not _IDENTIFIER_RE.fullmatch(value)
    ):
        raise ShaderCensusError(f"{label} is not a bounded identifier")
    return value


def _mask_comments(text: str, path: str) -> tuple[str, dict[str, int]]:
    masked = list(text)
    line_comments = 0
    block_comments = 0
    index = 0
    while index < len(text):
        if text[index] in {'"', "'"}:
            raise ShaderCensusError(f"{path}: string literals are unsupported")
        if text.startswith("//", index):
            line_comments += 1
            endings = [
                ending
                for ending in (
                    text.find("\r", index + 2),
                    text.find("\n", index + 2),
                )
                if ending >= 0
            ]
            end = min(endings, default=len(text))
            for cursor in range(index, end):
                if masked[cursor] not in "\r\n":
                    masked[cursor] = " "
            index = end
            continue
        if text.startswith("/*", index):
            block_comments += 1
            end = text.find("*/", index + 2)
            if end < 0:
                raise ShaderCensusError(f"{path}: unterminated block comment")
            for cursor in range(index, end + 2):
                if masked[cursor] not in "\r\n":
                    masked[cursor] = " "
            index = end + 2
            continue
        if text.startswith("*/", index):
            raise ShaderCensusError(f"{path}: unmatched block-comment close")
        index += 1
    return "".join(masked), {
        "line_comments": line_comments,
        "block_comments": block_comments,
    }


def _condition_symbols(body: str, path: str, line_number: int) -> list[str]:
    tokens: list[str] = []
    cursor = 0
    for match in _CONDITION_TOKEN_RE.finditer(body):
        if body[cursor : match.start()].strip():
            raise ShaderCensusError(
                f"{path}:{line_number}: unsupported conditional expression"
            )
        tokens.append(match.group())
        cursor = match.end()
    if body[cursor:].strip() or not tokens:
        raise ShaderCensusError(
            f"{path}:{line_number}: unsupported conditional expression"
        )
    if len(tokens) > MAX_PREPROCESSOR_EXPRESSION_TOKENS:
        raise ShaderCensusError(
            f"{path}:{line_number}: conditional expression exceeds token limit"
        )

    position = 0
    symbols: list[str] = []

    def peek() -> str | None:
        return tokens[position] if position < len(tokens) else None

    def parse_primary(depth: int) -> None:
        nonlocal position
        if depth > MAX_PREPROCESSOR_CONDITIONAL_DEPTH:
            raise ShaderCensusError(
                f"{path}:{line_number}: conditional expression is too deeply nested"
            )
        token = peek()
        if token == "(":
            position += 1
            parse_or(depth + 1)
            if peek() != ")":
                raise ShaderCensusError(
                    f"{path}:{line_number}: unbalanced conditional expression"
                )
            position += 1
            return
        if token == "defined":
            position += 1
            parenthesized = peek() == "("
            if parenthesized:
                position += 1
            symbol = peek()
            if symbol is None or not _IDENTIFIER_RE.fullmatch(symbol):
                raise ShaderCensusError(
                    f"{path}:{line_number}: defined needs one symbol"
                )
            symbols.append(
                _require_identifier(symbol, f"{path}:{line_number} symbol")
            )
            position += 1
            if parenthesized:
                if peek() != ")":
                    raise ShaderCensusError(
                        f"{path}:{line_number}: defined needs one symbol"
                    )
                position += 1
            return
        if token is not None and _IDENTIFIER_RE.fullmatch(token):
            symbols.append(
                _require_identifier(token, f"{path}:{line_number} symbol")
            )
            position += 1
            return
        if token is not None and token.isdecimal() and len(token) <= 32:
            position += 1
            return
        raise ShaderCensusError(
            f"{path}:{line_number}: unsupported conditional expression"
        )

    def parse_unary(depth: int) -> None:
        nonlocal position
        negations = 0
        while peek() == "!":
            position += 1
            negations += 1
            if negations > MAX_PREPROCESSOR_CONDITIONAL_DEPTH:
                raise ShaderCensusError(
                    f"{path}:{line_number}: conditional expression is too deeply nested"
                )
        parse_primary(depth + negations)

    def parse_and(depth: int) -> None:
        nonlocal position
        parse_unary(depth)
        while peek() == "&&":
            position += 1
            parse_unary(depth)

    def parse_or(depth: int) -> None:
        nonlocal position
        parse_and(depth)
        while peek() == "||":
            position += 1
            parse_and(depth)

    parse_or(0)
    if position != len(tokens):
        raise ShaderCensusError(
            f"{path}:{line_number}: unsupported conditional expression"
        )
    return symbols


def _preprocessor_facts(
    masked: str,
    path: str,
) -> tuple[str, dict[str, Any]]:
    directives: Counter[str] = Counter()
    read_symbols: Counter[str] = Counter()
    defined_symbols: Counter[str] = Counter()
    undefined_symbols: Counter[str] = Counter()
    conditional_stack: list[bool] = []
    maximum_depth = 0
    output_lines: list[str] = []
    for line_number, line in enumerate(masked.splitlines(keepends=True), start=1):
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            output_lines.append(line)
            continue
        match = _DIRECTIVE_RE.match(line.rstrip("\r\n"))
        if match is None:
            raise ShaderCensusError(
                f"{path}:{line_number}: malformed preprocessor directive"
            )
        directive = _require_identifier(
            match.group("directive"), f"{path}:{line_number} directive"
        )
        if directive not in _SUPPORTED_DIRECTIVES:
            raise ShaderCensusError(
                f"{path}:{line_number}: unsupported #{directive} directive"
            )
        body = match.group("body")
        identifiers = [
            _require_identifier(value, f"{path}:{line_number} symbol")
            for value in _IDENTIFIER_TOKEN_RE.findall(body)
            if value != "defined"
        ]
        directives[directive] += 1
        if directive in {"if", "ifdef", "ifndef"}:
            if directive in {"ifdef", "ifndef"} and not re.fullmatch(
                r"\s*[A-Za-z_][A-Za-z0-9_]*\s*", body
            ):
                raise ShaderCensusError(
                    f"{path}:{line_number}: #{directive} needs one symbol"
                )
            condition_symbols = (
                _condition_symbols(body, path, line_number)
                if directive == "if"
                else [body.strip()]
            )
            for symbol in condition_symbols:
                read_symbols[symbol] += 1
            conditional_stack.append(False)
            if len(conditional_stack) > MAX_PREPROCESSOR_CONDITIONAL_DEPTH:
                raise ShaderCensusError(
                    f"{path}:{line_number}: conditional nesting exceeds limit"
                )
            maximum_depth = max(maximum_depth, len(conditional_stack))
        elif directive == "elif":
            if not conditional_stack or conditional_stack[-1]:
                raise ShaderCensusError(f"{path}:{line_number}: unmatched #elif")
            for symbol in _condition_symbols(body, path, line_number):
                read_symbols[symbol] += 1
        elif directive == "else":
            if (
                not conditional_stack
                or conditional_stack[-1]
                or body.strip()
            ):
                raise ShaderCensusError(f"{path}:{line_number}: malformed #else")
            conditional_stack[-1] = True
        elif directive == "endif":
            if not conditional_stack or body.strip():
                raise ShaderCensusError(f"{path}:{line_number}: unmatched #endif")
            conditional_stack.pop()
        elif directive in {"define", "undef"}:
            symbol_match = re.match(
                r"\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)", body
            )
            if symbol_match is None or (
                directive == "undef"
                and not re.fullmatch(
                    r"\s*[A-Za-z_][A-Za-z0-9_]*\s*", body
                )
            ):
                raise ShaderCensusError(
                    f"{path}:{line_number}: #{directive} needs a symbol"
                )
            defined_name = _require_identifier(
                symbol_match.group("name"), f"{path}:{line_number} symbol"
            )
            destination = (
                defined_symbols if directive == "define" else undefined_symbols
            )
            destination[defined_name] += 1
            skipped_definition = False
            for symbol in identifiers:
                if not skipped_definition and symbol == defined_name:
                    skipped_definition = True
                    continue
                read_symbols[symbol] += 1
        newline = (
            "\r\n"
            if line.endswith("\r\n")
            else "\n"
            if line.endswith("\n")
            else "\r"
            if line.endswith("\r")
            else ""
        )
        output_lines.append(" " * (len(line) - len(newline)) + newline)
    if conditional_stack:
        raise ShaderCensusError(f"{path}: unterminated preprocessor conditional")
    return "".join(output_lines), {
        "directives": [
            {"directive": key, "occurrences": directives[key]}
            for key in sorted(directives)
        ],
        "read_symbols": [
            {"name": key, "occurrences": read_symbols[key]}
            for key in sorted(read_symbols)
        ],
        "defined_symbols": [
            {"name": key, "occurrences": defined_symbols[key]}
            for key in sorted(defined_symbols)
        ],
        "undefined_symbols": [
            {"name": key, "occurrences": undefined_symbols[key]}
            for key in sorted(undefined_symbols)
        ],
        "maximum_conditional_depth": maximum_depth,
    }


def _brace_depths(code: str, path: str) -> list[int]:
    depths = [0] * (len(code) + 1)
    depth = 0
    for index, character in enumerate(code):
        depths[index] = depth
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth < 0:
                raise ShaderCensusError(f"{path}: unmatched closing brace")
    depths[len(code)] = depth
    if depth:
        raise ShaderCensusError(f"{path}: unterminated brace scope")
    return depths


def _line_endings(text: str) -> dict[str, Any]:
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    cr = text.count("\r") - crlf
    present = sum(bool(value) for value in (crlf, lf, cr))
    style = (
        "none"
        if present == 0
        else "crlf"
        if crlf and present == 1
        else "lf"
        if lf and present == 1
        else "cr"
        if cr and present == 1
        else "mixed"
    )
    return {"style": style, "crlf": crlf, "lf": lf, "cr": cr}


def _parse_shader(
    *,
    path: str,
    size: int,
    sha256: str,
    text: str,
) -> dict[str, Any]:
    if text.startswith("\ufeff"):
        raise ShaderCensusError(f"{path}: UTF-8 BOM is unsupported")
    if any(
        ord(character) < 0x20 and character not in "\t\r\n"
        for character in text
    ):
        raise ShaderCensusError(f"{path}: unsupported control character")
    masked, comments = _mask_comments(text, path)
    code, preprocessor = _preprocessor_facts(masked, path)
    depths = _brace_depths(code, path)

    declarations = []
    recognized_top_level_spans: list[tuple[int, int]] = []
    declaration_starts: set[int] = set()
    declared_names: set[tuple[str, str]] = set()
    for match in _DECLARATION_RE.finditer(code):
        if depths[match.start()] != 0:
            raise ShaderCensusError(f"{path}: interface declaration is not top-level")
        record = {
            "storage": match.group("storage"),
            "precision": match.group("precision"),
            "type": _require_identifier(match.group("type"), f"{path} type"),
            "name": _require_identifier(match.group("name"), f"{path} name"),
        }
        key = (record["storage"], record["name"])
        if key in declared_names:
            raise ShaderCensusError(f"{path}: duplicate declaration {key}")
        declared_names.add(key)
        declaration_starts.add(match.start())
        recognized_top_level_spans.append(match.span())
        declarations.append(record)
    keyword_starts = {
        match.start() for match in _DECLARATION_KEYWORD_RE.finditer(code)
    }
    if keyword_starts != declaration_starts:
        raise ShaderCensusError(f"{path}: unsupported interface declaration shape")

    main_matches = [
        match for match in _MAIN_RE.finditer(code) if depths[match.start()] == 0
    ]
    if len(main_matches) > 1:
        raise ShaderCensusError(f"{path}: multiple main entry points")
    top_level_open_braces = {
        index
        for index, character in enumerate(code)
        if character == "{" and depths[index] == 0
    }
    main_open_braces = {match.end() - 1 for match in main_matches}
    if top_level_open_braces != main_open_braces:
        raise ShaderCensusError(f"{path}: unsupported top-level block")
    for match in main_matches:
        open_brace = match.end() - 1
        close_brace = next(
            (
                index
                for index in range(open_brace + 1, len(code))
                if code[index] == "}" and depths[index] == 1
            ),
            None,
        )
        if close_brace is None:
            raise ShaderCensusError(f"{path}: unterminated main entry point")
        recognized_top_level_spans.append((match.start(), close_brace + 1))
    cursor = 0
    for start, end in sorted(recognized_top_level_spans):
        if start < cursor or code[cursor:start].strip():
            raise ShaderCensusError(f"{path}: unsupported top-level syntax")
        cursor = end
    if code[cursor:].strip():
        raise ShaderCensusError(f"{path}: unsupported top-level syntax")

    main_name_offsets = {
        match.start("name") for match in main_matches
    }
    calls: Counter[str] = Counter()
    for match in _CALL_RE.finditer(code):
        name = _require_identifier(match.group("name"), f"{path} call")
        if match.start("name") in main_name_offsets or name in _CONTROL_CALL_NAMES:
            continue
        calls[name] += 1
    builtins = Counter(_BUILTIN_RE.findall(code))
    builtin_writes = Counter(
        match.group("name")
        for match in re.finditer(
            r"\b(?P<name>gl_[A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)", code
        )
    )
    extension = PurePosixPath(path).suffix.casefold()
    return {
        "path": path,
        "size": size,
        "sha256": sha256,
        "extension": extension,
        "stage": _ALLOWED_EXTENSIONS[extension],
        "encoding": "utf-8-no-bom",
        "line_count": len(text.splitlines()),
        "line_endings": _line_endings(text),
        "comments": comments,
        "entry_points": ["main"] if main_matches else [],
        "interface_declarations": declarations,
        "preprocessor": preprocessor,
        "call_identifiers": [
            {"name": name, "occurrences": calls[name]} for name in sorted(calls)
        ],
        "builtin_identifiers": [
            {
                "name": name,
                "occurrences": builtins[name],
                "write_occurrences": builtin_writes[name],
            }
            for name in sorted(builtins)
        ],
        "discard_occurrences": len(re.findall(r"\bdiscard\b", code)),
        "identifier_tokens": len(_IDENTIFIER_TOKEN_RE.findall(code)),
        "numeric_tokens": len(_NUMBER_TOKEN_RE.findall(code)),
        "semicolon_tokens": code.count(";"),
    }


def build_shader_census(
    install_root: Path,
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Inventory and parse the shader interface surface without publishing source."""
    if not isinstance(inventory, Mapping):
        raise ShaderCensusError("inventory must be an object")
    content_root, identity = _attest_installation(install_root, inventory)
    manifest = _shader_manifest(content_root)
    files = []
    for entry in manifest["files"]:
        path = str(entry["path"])
        try:
            text = read_exact_inventory_file(
                content_root,
                PurePosixPath(path),
                expected_size=entry["size"],
                expected_sha256=entry["sha256"],
            )
        except WeaponCoverageError as exc:
            raise ShaderCensusError(f"{path}: {exc}") from exc
        if len(text.encode("utf-8")) != entry["size"]:
            raise ShaderCensusError(f"UTF-8 round trip changed source bytes: {path}")
        files.append(
            _parse_shader(
                path=path,
                size=entry["size"],
                sha256=entry["sha256"],
                text=text,
            )
        )

    interface_counts: Counter[tuple[str, str, str | None, str]] = Counter()
    interface_files: dict[tuple[str, str, str | None, str], set[str]] = defaultdict(set)
    preprocessor_counts: Counter[tuple[str, str]] = Counter()
    preprocessor_files: dict[tuple[str, str], set[str]] = defaultdict(set)
    call_counts: Counter[str] = Counter()
    call_files: dict[str, set[str]] = defaultdict(set)
    for file in files:
        for declaration in file["interface_declarations"]:
            key = (
                declaration["storage"],
                declaration["type"],
                declaration["precision"],
                declaration["name"],
            )
            interface_counts[key] += 1
            interface_files[key].add(file["path"])
        for category in ("read_symbols", "defined_symbols", "undefined_symbols"):
            for symbol in file["preprocessor"][category]:
                key = (category, symbol["name"])
                preprocessor_counts[key] += symbol["occurrences"]
                preprocessor_files[key].add(file["path"])
        for call in file["call_identifiers"]:
            call_counts[call["name"]] += call["occurrences"]
            call_files[call["name"]].add(file["path"])

    hash_groups: dict[str, list[str]] = defaultdict(list)
    for file in files:
        hash_groups[file["sha256"]].append(file["path"])
    duplicate_groups = [
        {"sha256": sha256, "paths": sorted(paths)}
        for sha256, paths in sorted(hash_groups.items())
        if len(paths) > 1
    ]
    stage_counts = Counter(file["stage"] for file in files)
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": identity,
        "baseline_inventory": {
            "label": inventory.get("label"),
            "canonical_sha256": _canonical_sha256(inventory),
        },
        "shader_manifest": {
            key: manifest[key]
            for key in ("root", "file_count", "byte_count", "revision_sha256")
        },
        "method": {
            "source_execution": False,
            "compiler_invocation": False,
            "stage_classification": "filename-extension hint only",
            "parser": (
                "bounded UTF-8 lexical scan with comment masking, balanced "
                "preprocessor/braces, strict top-level interface declarations, "
                "and a void main() entry-point subset"
            ),
            "publication_policy": (
                "file identities, bounded interface/preprocessor/call identifiers, "
                "and counts only; no raw source, expressions, literals, or bodies"
            ),
            "limitations": [
                "extension hints do not prove stage compilation or runtime loading",
                "source alone does not prove header prepending or macro configurations",
                "filename similarity does not prove pipeline pairing",
                "no OpenGL version, driver acceptance, locations, values, "
                "reachability, or render semantics are inferred",
            ],
        },
        "files": files,
        "interfaces": [
            {
                "storage": key[0],
                "type": key[1],
                "precision": key[2],
                "name": key[3],
                "declarations": interface_counts[key],
                "source_files": sorted(interface_files[key]),
            }
            for key in sorted(
                interface_counts,
                key=lambda value: tuple(str(x) for x in value),
            )
        ],
        "preprocessor_symbols": [
            {
                "role": key[0],
                "name": key[1],
                "occurrences": preprocessor_counts[key],
                "source_files": sorted(preprocessor_files[key]),
            }
            for key in sorted(preprocessor_counts)
        ],
        "call_identifiers": [
            {
                "name": name,
                "occurrences": call_counts[name],
                "source_files": sorted(call_files[name]),
            }
            for name in sorted(call_counts)
        ],
        "duplicate_content_groups": duplicate_groups,
        "summary": {
            "shader_files": len(files),
            "shader_bytes": sum(file["size"] for file in files),
            "stage_hints": [
                {"stage": stage, "files": stage_counts[stage]}
                for stage in sorted(stage_counts)
            ],
            "entry_points": sum(len(file["entry_points"]) for file in files),
            "interface_declarations": sum(
                len(file["interface_declarations"]) for file in files
            ),
            "interface_identifiers": len({key[3] for key in interface_counts}),
            "uniform_identifiers": len(
                {key[3] for key in interface_counts if key[0] == "uniform"}
            ),
            "attribute_identifiers": len(
                {key[3] for key in interface_counts if key[0] == "attribute"}
            ),
            "varying_identifiers": len(
                {key[3] for key in interface_counts if key[0] == "varying"}
            ),
            "preprocessor_symbols": len(
                {key[1] for key in preprocessor_counts}
            ),
            "call_identifiers": len(call_counts),
            "texture2d_calls": call_counts["texture2D"],
            "discard_occurrences": sum(
                file["discard_occurrences"] for file in files
            ),
            "duplicate_content_groups": len(duplicate_groups),
            "mixed_line_ending_files": sum(
                file["line_endings"]["style"] == "mixed" for file in files
            ),
            "schema_violations": 0,
        },
    }


def validate_shader_census(
    install_root: Path,
    evidence: Mapping[str, Any],
    *,
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild and exact-compare a normalized shader census."""
    if not isinstance(evidence, Mapping):
        raise ShaderCensusError("evidence must be an object")
    expected = build_shader_census(install_root, inventory=inventory)
    if evidence != expected:
        raise ShaderCensusError(
            "shader census does not match the exact installation and inventory"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": VERIFICATION_KIND,
        "status": "verified",
        "build_identity": expected["build_identity"],
        "evidence_sha256": _canonical_sha256(evidence),
        "summary": expected["summary"],
    }


def encode_shader_census(value: Mapping[str, Any]) -> str:
    """Encode census or verification output deterministically."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
