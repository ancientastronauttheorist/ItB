"""Strict parser for the non-executable Lua data subset used by ITB maps."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypeAlias


_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_INTEGER_RE = re.compile(r"[0-9]+")
_MAX_INTEGER_DIGITS = 10
_MAX_SOURCE_CHARACTERS = 16 * 1024 * 1024
_MAX_STRING_CHARACTERS = 4_096
_MAX_TOKENS = 100_000
_MAX_TABLE_ENTRIES = 10_000
_MAX_TABLE_DEPTH = 32
_LUA_RESERVED_WORDS = frozenset(
    {
        "and",
        "break",
        "do",
        "else",
        "elseif",
        "end",
        "false",
        "for",
        "function",
        "goto",
        "if",
        "in",
        "local",
        "nil",
        "not",
        "or",
        "repeat",
        "return",
        "then",
        "true",
        "until",
        "while",
    }
)


class LuaDataError(RuntimeError):
    """Raised when input leaves the accepted non-executable Lua data grammar."""


@dataclass(frozen=True)
class LuaPoint:
    x: int
    y: int


@dataclass(frozen=True)
class LuaTableEntry:
    key: str | None
    value: "LuaValue"


@dataclass(frozen=True)
class LuaTable:
    entries: tuple[LuaTableEntry, ...]

    def keyed(self) -> dict[str, "LuaValue"]:
        result: dict[str, LuaValue] = {}
        for entry in self.entries:
            if entry.key is None:
                continue
            if entry.key in result:
                raise LuaDataError(f"duplicate Lua table key: {entry.key}")
            result[entry.key] = entry.value
        return result

    def array(self) -> tuple["LuaValue", ...]:
        return tuple(entry.value for entry in self.entries if entry.key is None)

    def require_pure_keyed(self, label: str) -> dict[str, "LuaValue"]:
        if any(entry.key is None for entry in self.entries):
            raise LuaDataError(f"{label} must not contain array entries")
        return self.keyed()

    def require_pure_array(self, label: str) -> tuple["LuaValue", ...]:
        if any(entry.key is not None for entry in self.entries):
            raise LuaDataError(f"{label} must not contain keyed entries")
        return self.array()


LuaValue: TypeAlias = int | str | bool | LuaPoint | LuaTable


@dataclass(frozen=True)
class LuaDataChunk:
    global_name: str
    value: LuaTable


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    offset: int


class _Lexer:
    def __init__(self, text: str) -> None:
        self.text = text
        self.offset = 0
        self.token_count = 0

    def _token(self, kind: str, value: str, offset: int) -> _Token:
        if kind != "EOF":
            self.token_count += 1
            if self.token_count > _MAX_TOKENS:
                raise LuaDataError(
                    f"Lua data exceeds the {_MAX_TOKENS}-token limit"
                )
        return _Token(kind, value, offset)

    def _skip_space_and_comments(self) -> None:
        while self.offset < len(self.text):
            if self.text[self.offset].isspace():
                self.offset += 1
                continue
            if self.text.startswith("--", self.offset):
                newline = self.text.find("\n", self.offset + 2)
                self.offset = len(self.text) if newline < 0 else newline + 1
                continue
            return

    def next(self) -> _Token:
        self._skip_space_and_comments()
        start = self.offset
        if start >= len(self.text):
            return self._token("EOF", "", start)
        character = self.text[start]
        if character in "{}[](),=":
            self.offset += 1
            return self._token(character, character, start)
        if character in {"'", '"'}:
            quote = character
            cursor = start + 1
            while cursor < len(self.text) and self.text[cursor] != quote:
                if self.text[cursor] == "\\":
                    raise LuaDataError(
                        f"Lua string escapes are outside the data grammar at {cursor}"
                    )
                if self.text[cursor] in "\r\n":
                    raise LuaDataError(f"newline in Lua short string at {cursor}")
                if cursor - start > _MAX_STRING_CHARACTERS:
                    raise LuaDataError(
                        "Lua data string exceeds the "
                        f"{_MAX_STRING_CHARACTERS}-character limit at {start}"
                    )
                cursor += 1
            if cursor >= len(self.text):
                raise LuaDataError(f"unterminated Lua string at {start}")
            self.offset = cursor + 1
            return self._token(
                "STRING", self.text[start + 1 : cursor], start
            )
        identifier = _IDENTIFIER_RE.match(self.text, start)
        if identifier:
            self.offset = identifier.end()
            return self._token("IDENT", identifier.group(), start)
        integer = _INTEGER_RE.match(self.text, start)
        if integer:
            self.offset = integer.end()
            return self._token("INTEGER", integer.group(), start)
        raise LuaDataError(
            f"unsupported Lua data token {character!r} at offset {start}"
        )


class _Parser:
    def __init__(self, text: str) -> None:
        self.lexer = _Lexer(text)
        self.table_entry_count = 0
        self.lookahead = self.lexer.next()

    def _take(self, kind: str) -> _Token:
        if self.lookahead.kind != kind:
            raise LuaDataError(
                f"expected {kind} at offset {self.lookahead.offset}, "
                f"found {self.lookahead.kind}"
            )
        token = self.lookahead
        self.lookahead = self.lexer.next()
        return token

    def parse(self) -> LuaDataChunk:
        global_name = self._take("IDENT").value
        if global_name == "Point" or global_name in _LUA_RESERVED_WORDS:
            raise LuaDataError("invalid Lua data chunk global name")
        self._take("=")
        value = self._table(depth=1)
        self._take("EOF")
        return LuaDataChunk(global_name=global_name, value=value)

    def _value(self) -> LuaValue:
        if self.lookahead.kind == "STRING":
            return self._take("STRING").value
        if self.lookahead.kind == "INTEGER":
            return self._integer()
        if self.lookahead.kind == "{":
            return self._table(depth=self.table_depth + 1)
        if self.lookahead.kind == "IDENT":
            identifier = self._take("IDENT").value
            if identifier == "true":
                return True
            if identifier == "false":
                return False
            if identifier == "Point":
                self._take("(")
                x = self._integer()
                self._take(",")
                y = self._integer()
                self._take(")")
                return LuaPoint(x=x, y=y)
            raise LuaDataError(f"unsupported Lua data identifier: {identifier}")
        raise LuaDataError(
            f"expected Lua data value at offset {self.lookahead.offset}"
        )

    def _integer(self) -> int:
        token = self._take("INTEGER")
        if len(token.value) > _MAX_INTEGER_DIGITS:
            raise LuaDataError(
                f"Lua data integer exceeds {_MAX_INTEGER_DIGITS} digits "
                f"at offset {token.offset}"
            )
        return int(token.value)

    def _table(self, *, depth: int) -> LuaTable:
        if depth > _MAX_TABLE_DEPTH:
            raise LuaDataError(
                f"Lua data table nesting exceeds {_MAX_TABLE_DEPTH} levels"
            )
        previous_depth = getattr(self, "table_depth", 0)
        self.table_depth = depth
        self._take("{")
        entries: list[LuaTableEntry] = []
        try:
            while self.lookahead.kind != "}":
                if self.lookahead.kind == "[":
                    self._take("[")
                    key = self._take("STRING").value
                    self._take("]")
                    self._take("=")
                    value = self._value()
                else:
                    key = None
                    value = self._value()
                self.table_entry_count += 1
                if self.table_entry_count > _MAX_TABLE_ENTRIES:
                    raise LuaDataError(
                        "Lua data exceeds the "
                        f"{_MAX_TABLE_ENTRIES}-table-entry limit"
                    )
                entries.append(LuaTableEntry(key=key, value=value))
                if self.lookahead.kind == ",":
                    self._take(",")
                elif self.lookahead.kind != "}":
                    raise LuaDataError(
                        f"expected comma at offset {self.lookahead.offset}"
                    )
            self._take("}")
            return LuaTable(entries=tuple(entries))
        finally:
            self.table_depth = previous_depth


def parse_lua_data_chunk(text: str) -> LuaDataChunk:
    """Parse exactly one ``global = table`` chunk without executing Lua."""
    if type(text) is not str:
        raise LuaDataError("Lua data input must be text")
    if len(text) > _MAX_SOURCE_CHARACTERS:
        raise LuaDataError(
            "Lua data input exceeds the "
            f"{_MAX_SOURCE_CHARACTERS}-character limit"
        )
    return _Parser(text).parse()
