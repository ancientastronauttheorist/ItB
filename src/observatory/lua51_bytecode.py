"""Strict metadata parser for Lua 5.1 binary chunks.

The parser retains structural/debug metadata and decoded instructions in
memory so callers can build inventories.  It never serializes bytecode or
literal payloads by itself.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


LUA51_SIGNATURE = b"\x1bLua"
LUA51_VERSION = 0x51
LUA51_FORMAT = 0
MAX_CHUNK_BYTES = 512 * 1024 * 1024
MAX_VECTOR_ITEMS = 10_000_000
MAX_PROTOTYPES = 1_000_000
MAX_RECURSION_DEPTH = 2_048
OPCODE_NAMES = (
    "MOVE",
    "LOADK",
    "LOADBOOL",
    "LOADNIL",
    "GETUPVAL",
    "GETGLOBAL",
    "GETTABLE",
    "SETGLOBAL",
    "SETUPVAL",
    "SETTABLE",
    "NEWTABLE",
    "SELF",
    "ADD",
    "SUB",
    "MUL",
    "DIV",
    "MOD",
    "POW",
    "UNM",
    "NOT",
    "LEN",
    "CONCAT",
    "JMP",
    "EQ",
    "LT",
    "LE",
    "TEST",
    "TESTSET",
    "CALL",
    "TAILCALL",
    "RETURN",
    "FORLOOP",
    "FORPREP",
    "TFORLOOP",
    "SETLIST",
    "CLOSE",
    "CLOSURE",
    "VARARG",
)
_IDENTIFIER_RE = re.compile(rb"[A-Za-z_][A-Za-z0-9_]*\Z")
_BITRK = 1 << 8


class Lua51BytecodeError(RuntimeError):
    """Raised when a Lua 5.1 binary chunk is malformed or unsupported."""


@dataclass(frozen=True)
class Lua51Header:
    little_endian: bool
    int_size: int
    size_t_size: int
    instruction_size: int
    number_size: int
    number_is_integral: bool

    def normalized(self) -> dict[str, int | bool | str]:
        return {
            "signature": LUA51_SIGNATURE.hex(),
            "version": "5.1",
            "format": LUA51_FORMAT,
            "little_endian": self.little_endian,
            "int_size": self.int_size,
            "size_t_size": self.size_t_size,
            "instruction_size": self.instruction_size,
            "number_size": self.number_size,
            "number_is_integral": self.number_is_integral,
        }


@dataclass(frozen=True)
class Lua51Local:
    name: bytes
    start_pc: int
    end_pc: int


@dataclass(frozen=True)
class Lua51Prototype:
    prototype_path: str
    source: bytes | None
    line_defined: int
    last_line_defined: int
    upvalue_count: int
    parameter_count: int
    vararg_flags: int
    max_stack_size: int
    instructions: tuple[int, ...]
    string_constants: tuple[bytes | None, ...]
    constant_count: int
    children: tuple["Lua51Prototype", ...]
    line_info: tuple[int, ...]
    locals: tuple[Lua51Local, ...]
    upvalue_names: tuple[bytes, ...]
    serialized_sha256: str
    serialized_size: int


@dataclass(frozen=True)
class Lua51Chunk:
    header: Lua51Header
    root: Lua51Prototype
    sha256: str
    size: int


class _Reader:
    def __init__(self, data: bytes) -> None:
        if len(data) > MAX_CHUNK_BYTES:
            raise Lua51BytecodeError("Lua bytecode exceeds the analysis size limit")
        self.data = data
        self.offset = 0
        self.header: Lua51Header | None = None
        self.prototype_count = 0

    def read(self, size: int, label: str) -> bytes:
        if size < 0 or self.offset + size > len(self.data):
            raise Lua51BytecodeError(f"truncated Lua bytecode while reading {label}")
        value = self.data[self.offset : self.offset + size]
        self.offset += size
        return value

    def byte(self, label: str) -> int:
        return self.read(1, label)[0]

    @property
    def byteorder(self) -> str:
        if self.header is None:
            raise Lua51BytecodeError("Lua bytecode header is unavailable")
        return "little" if self.header.little_endian else "big"

    def integer(self, label: str) -> int:
        if self.header is None:
            raise Lua51BytecodeError("Lua bytecode header is unavailable")
        return int.from_bytes(
            self.read(self.header.int_size, label),
            self.byteorder,
            signed=True,
        )

    def count(self, label: str) -> int:
        value = self.integer(label)
        if value < 0 or value > MAX_VECTOR_ITEMS:
            raise Lua51BytecodeError(f"implausible {label}: {value}")
        return value

    def size_t(self, label: str) -> int:
        if self.header is None:
            raise Lua51BytecodeError("Lua bytecode header is unavailable")
        value = int.from_bytes(
            self.read(self.header.size_t_size, label),
            self.byteorder,
            signed=False,
        )
        if value > MAX_CHUNK_BYTES:
            raise Lua51BytecodeError(f"implausible {label}: {value}")
        return value

    def string(self, label: str) -> bytes | None:
        size = self.size_t(f"{label} size")
        if size == 0:
            return None
        raw = self.read(size, label)
        if raw[-1:] != b"\0":
            raise Lua51BytecodeError(f"{label} is not NUL terminated")
        return raw[:-1]


def _read_header(reader: _Reader) -> Lua51Header:
    if reader.read(4, "signature") != LUA51_SIGNATURE:
        raise Lua51BytecodeError("input is not a Lua binary chunk")
    if reader.byte("version") != LUA51_VERSION:
        raise Lua51BytecodeError("input is not Lua 5.1 bytecode")
    if reader.byte("format") != LUA51_FORMAT:
        raise Lua51BytecodeError("unsupported Lua bytecode format")
    endian = reader.byte("endianness")
    int_size = reader.byte("sizeof(int)")
    size_t_size = reader.byte("sizeof(size_t)")
    instruction_size = reader.byte("sizeof(Instruction)")
    number_size = reader.byte("sizeof(lua_Number)")
    integral = reader.byte("lua_Number integral flag")
    if endian not in (0, 1):
        raise Lua51BytecodeError("invalid Lua bytecode endianness flag")
    if int_size != 4:
        raise Lua51BytecodeError(f"unsupported Lua int size: {int_size}")
    if size_t_size not in (4, 8):
        raise Lua51BytecodeError(f"unsupported Lua size_t size: {size_t_size}")
    if instruction_size != 4:
        raise Lua51BytecodeError(
            f"unsupported Lua instruction size: {instruction_size}"
        )
    if number_size not in (4, 8):
        raise Lua51BytecodeError(f"unsupported Lua number size: {number_size}")
    if integral not in (0, 1):
        raise Lua51BytecodeError("invalid Lua number integral flag")
    return Lua51Header(
        little_endian=bool(endian),
        int_size=int_size,
        size_t_size=size_t_size,
        instruction_size=instruction_size,
        number_size=number_size,
        number_is_integral=bool(integral),
    )


def _read_prototype(
    reader: _Reader,
    *,
    prototype_path: str,
    inherited_source: bytes | None,
    depth: int,
) -> Lua51Prototype:
    if depth > MAX_RECURSION_DEPTH:
        raise Lua51BytecodeError("Lua prototype nesting exceeds the analysis limit")
    reader.prototype_count += 1
    if reader.prototype_count > MAX_PROTOTYPES:
        raise Lua51BytecodeError("Lua prototype count exceeds the analysis limit")
    start = reader.offset
    source = reader.string(f"prototype {prototype_path} source")
    effective_source = inherited_source if source is None else source
    line_defined = reader.integer(f"prototype {prototype_path} line defined")
    last_line_defined = reader.integer(
        f"prototype {prototype_path} last line defined"
    )
    if line_defined < 0 or last_line_defined < line_defined:
        raise Lua51BytecodeError(
            f"prototype {prototype_path} has an invalid source line range"
        )
    upvalue_count = reader.byte(f"prototype {prototype_path} upvalue count")
    parameter_count = reader.byte(f"prototype {prototype_path} parameter count")
    vararg_flags = reader.byte(f"prototype {prototype_path} vararg flags")
    max_stack_size = reader.byte(f"prototype {prototype_path} max stack size")

    instruction_count = reader.count(
        f"prototype {prototype_path} instruction count"
    )
    instructions = tuple(
        int.from_bytes(
            reader.read(4, f"prototype {prototype_path} instruction {index}"),
            reader.byteorder,
            signed=False,
        )
        for index in range(instruction_count)
    )
    for index, instruction in enumerate(instructions):
        opcode = instruction & 0x3F
        if opcode >= len(OPCODE_NAMES):
            raise Lua51BytecodeError(
                f"prototype {prototype_path} instruction {index} has "
                f"invalid opcode {opcode}"
            )

    constant_count = reader.count(f"prototype {prototype_path} constant count")
    string_constants: list[bytes | None] = []
    for index in range(constant_count):
        tag = reader.byte(f"prototype {prototype_path} constant {index} tag")
        if tag == 0:
            string_constants.append(None)
        elif tag == 1:
            boolean = reader.byte(
                f"prototype {prototype_path} constant {index} boolean"
            )
            if boolean not in (0, 1):
                raise Lua51BytecodeError(
                    f"prototype {prototype_path} constant {index} has "
                    "an invalid boolean"
                )
            string_constants.append(None)
        elif tag == 3:
            if reader.header is None:
                raise Lua51BytecodeError("Lua bytecode header is unavailable")
            reader.read(
                reader.header.number_size,
                f"prototype {prototype_path} constant {index} number",
            )
            string_constants.append(None)
        elif tag == 4:
            value = reader.string(
                f"prototype {prototype_path} constant {index} string"
            )
            if value is None:
                raise Lua51BytecodeError(
                    f"prototype {prototype_path} string constant is null"
                )
            string_constants.append(value)
        else:
            raise Lua51BytecodeError(
                f"prototype {prototype_path} constant {index} has "
                f"unsupported tag {tag}"
            )

    child_count = reader.count(f"prototype {prototype_path} child count")
    children = tuple(
        _read_prototype(
            reader,
            prototype_path=f"{prototype_path}/{index}",
            inherited_source=effective_source,
            depth=depth + 1,
        )
        for index in range(child_count)
    )
    line_info_count = reader.count(f"prototype {prototype_path} line-info count")
    line_info = tuple(
        reader.integer(f"prototype {prototype_path} line-info {index}")
        for index in range(line_info_count)
    )
    if line_info_count not in (0, instruction_count):
        raise Lua51BytecodeError(
            f"prototype {prototype_path} line-info length does not match code"
        )
    if any(line < 0 for line in line_info):
        raise Lua51BytecodeError(
            f"prototype {prototype_path} contains a negative source line"
        )

    local_count = reader.count(f"prototype {prototype_path} local count")
    locals_: list[Lua51Local] = []
    for index in range(local_count):
        name = reader.string(f"prototype {prototype_path} local {index} name")
        if name is None:
            raise Lua51BytecodeError(
                f"prototype {prototype_path} local {index} has no name"
            )
        start_pc = reader.integer(
            f"prototype {prototype_path} local {index} start PC"
        )
        end_pc = reader.integer(f"prototype {prototype_path} local {index} end PC")
        if start_pc < 0 or end_pc < start_pc or end_pc > instruction_count:
            raise Lua51BytecodeError(
                f"prototype {prototype_path} local {index} has an invalid PC range"
            )
        locals_.append(Lua51Local(name=name, start_pc=start_pc, end_pc=end_pc))

    upvalue_name_count = reader.count(
        f"prototype {prototype_path} upvalue-name count"
    )
    upvalue_names: list[bytes] = []
    for index in range(upvalue_name_count):
        name = reader.string(
            f"prototype {prototype_path} upvalue name {index}"
        )
        if name is None:
            raise Lua51BytecodeError(
                f"prototype {prototype_path} upvalue name {index} is null"
            )
        upvalue_names.append(name)
    if upvalue_name_count not in (0, upvalue_count):
        raise Lua51BytecodeError(
            f"prototype {prototype_path} upvalue-name count does not match"
        )

    end = reader.offset
    return Lua51Prototype(
        prototype_path=prototype_path,
        source=effective_source,
        line_defined=line_defined,
        last_line_defined=last_line_defined,
        upvalue_count=upvalue_count,
        parameter_count=parameter_count,
        vararg_flags=vararg_flags,
        max_stack_size=max_stack_size,
        instructions=instructions,
        string_constants=tuple(string_constants),
        constant_count=constant_count,
        children=children,
        line_info=line_info,
        locals=tuple(locals_),
        upvalue_names=tuple(upvalue_names),
        serialized_sha256=hashlib.sha256(reader.data[start:end]).hexdigest(),
        serialized_size=end - start,
    )


def parse_lua51_chunk(data: bytes) -> Lua51Chunk:
    """Parse one complete Lua 5.1 binary chunk or reject it strictly."""
    reader = _Reader(data)
    header = _read_header(reader)
    reader.header = header
    root = _read_prototype(
        reader,
        prototype_path="0",
        inherited_source=None,
        depth=0,
    )
    if reader.offset != len(data):
        raise Lua51BytecodeError("Lua bytecode contains trailing bytes")
    return Lua51Chunk(
        header=header,
        root=root,
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
    )


def flatten_prototypes(root: Lua51Prototype) -> list[Lua51Prototype]:
    """Return prototypes in stable tree/preorder order."""
    result = [root]
    for child in root.children:
        result.extend(flatten_prototypes(child))
    return result


def instruction_opcode(instruction: int) -> int:
    return instruction & 0x3F


def instruction_a(instruction: int) -> int:
    return (instruction >> 6) & 0xFF


def instruction_b(instruction: int) -> int:
    return (instruction >> 23) & 0x1FF


def instruction_c(instruction: int) -> int:
    return (instruction >> 14) & 0x1FF


def instruction_bx(instruction: int) -> int:
    return (instruction >> 14) & 0x3FFFF


def rk_constant_index(argument: int) -> int | None:
    return argument & 0xFF if argument & _BITRK else None


def identifier_constant(
    prototype: Lua51Prototype,
    index: int,
    *,
    label: str,
) -> str:
    if index < 0 or index >= prototype.constant_count:
        raise Lua51BytecodeError(
            f"prototype {prototype.prototype_path} has an invalid {label} "
            f"constant index {index}"
        )
    raw = prototype.string_constants[index]
    if raw is None or not _IDENTIFIER_RE.fullmatch(raw):
        raise Lua51BytecodeError(
            f"prototype {prototype.prototype_path} {label} is not an identifier"
        )
    return raw.decode("ascii")
