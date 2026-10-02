"""Finite continuous normal record copy with eight empty strings and empty path.

No allocator, scalar path copy, destructor or cookie checker is selected.
This proves synthetic pages and supplied normal state, not gameplay ownership.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from src.observatory import native_assertion_helper_fill_conformance as common
from src.observatory import native_movement_effect_record_empty_copy_semantics as model

BASE, EXE_SHA256 = common.BASE, common.EXE_SHA256
ANALYSIS_KIND = "pe_native_movement_effect_record_empty_copy_conformance"
SEALED_SHA256 = "e7a534fde897fc1e7520c1de8e8d7f9bb2a7fad6a33520c3fc70f396fe8c024d"
POINTS_SHA256 = "45e4d085df78b3abdcc5b54404ebc16a36a8fb8ca41ec1c7c0eab9083c3d76df"
SOURCE_PINS = dict(model.SOURCE_PINS)
REGISTERS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple(f"xmm{i}" for i in range(8))
STACK, SOURCE_PAGE, DEST_PAGE, COOKIE, RETURN = (
    0x30000000,
    0x10000000,
    0x10002000,
    0x893F28,
    0x4000000,
)
CPU_MODEL = 19
BODY_PINS = {
    0x15B9B0: (772, "3846fdb1ca2ebc1b4b6e83a64994f82d4907938345ff0d856c9bbea690957fc6"),
    0x80D0: (288, "062ae02111f4145fc3b614c93355bc20d6ae59544117d4c8bdcff4d82c488333"),
    0x9A8E0: (79, "4359ecaf051506bce97afe182b66c453ca8d13ac4091d72a810f9df43d14d2e0"),
    0x9AC40: (87, "29a0428ed018a85e4e0a76f283f10040cf9e084f49bee5706b58766b570cb9d1"),
}
BODIES = tuple(sorted((start, size) for start, (size, _) in BODY_PINS.items()))
STRING_OFFSETS = (0x38, 0x50, 0x68, 0x80, 0xA4, 0xE0, 0xF8, 0x118)
STRING_RETURNS = (
    0x55BA65,
    0x55BA99,
    0x55BACA,
    0x55BB01,
    0x55BB5C,
    0x55BC19,
    0x55BC50,
    0x55BC93,
)
FIELD_WIDTHS = tuple(
    (offset, 4)
    for offset in (
        0,
        4,
        8,
        12,
        16,
        0x18,
        0x1C,
        0x20,
        0x24,
        0x28,
        0x2C,
        0x34,
        0x98,
        0x9C,
        0xA0,
        0xBC,
        0xC0,
        0xC8,
        0xD8,
        0xDC,
        0x110,
        0x114,
        0x130,
    )
) + tuple((offset, 1) for offset in (0x14, 0x30, 0x31, 0xC4, 0xC5, 0xC6, 0xC7))
VECTOR_KEYS = {"alignment", "profile"}
FIXTURE_KEYS = {"pages", "registers", "xmm", "return_address", "entry_flags"}
EXPECTED_KEYS = {
    "source_address",
    "record_address",
    "record_bytes",
    "source_snapshot",
    "registers",
    "xmm",
    "pages",
    "events",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "trace_rvas",
    "boundaries",
}
BOUNDARY_KEYS = {
    "kind",
    "name",
    "index",
    "registers",
    "xmm",
    "pages",
    "events",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
}
_canonical_sha256, _canonical_bytes = common._canonical_sha256, common._canonical_bytes


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def _normalize(operation):
    try:
        return operation()
    except ConformanceError:
        raise
    except Exception as exc:
        raise ConformanceError(str(exc)) from exc


def _same_packet(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(
            any(type(k) is type(j) and k == j for j in right)
            and _same_packet(left[k], right[k])
            for k in left
        )
    if type(left) in (list, tuple):
        return len(left) == len(right) and all(
            _same_packet(a, b) for a, b in zip(left, right)
        )
    return left == right


def _read(pages, address, width=4):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(width)
    )


def _write(pages, address, payload):
    for i, byte in enumerate(payload):
        pages[(address + i) & ~4095][(address + i) & 4095] = byte


def _pages(pages):
    return {page: bytes(data) for page, data in pages.items()}


def _page_hashes(pages):
    return {
        f"0x{page:08x}": hashlib.sha256(data).hexdigest()
        for page, data in sorted(pages.items())
    }


def vectors():
    return [dict(alignment=a, profile=p) for a in range(16) for p in range(3)]


def _checked_vector(vector):
    _require(
        type(vector) is dict
        and set(vector) == VECTOR_KEYS
        and all(type(k) is str for k in vector)
        and all(type(v) is int for v in vector.values())
        and vector in vectors(),
        "outside fixed empty record copy domain",
    )


def _fixture(vector):
    _checked_vector(vector)
    a, p = vector["alignment"], vector["profile"]
    g, s, d = STACK + 4096 + a, SOURCE_PAGE + 0xFF0 + a, DEST_PAGE + 0xFF0 + a
    pages = {
        page: bytearray((i * 31 + j * 23 + p * 67) & 255 for j in range(4096))
        for i, page in enumerate(
            (
                0,
                STACK,
                STACK + 4096,
                SOURCE_PAGE,
                SOURCE_PAGE + 4096,
                DEST_PAGE,
                DEST_PAGE + 4096,
                COOKIE & ~4095,
            )
        )
    }
    cookie = (0x6D3FA172 ^ (p * 0x11111111)) & 0xFFFFFFFF
    for at, value in (
        (g, RETURN),
        (g + 4, s),
        (0, (0x1234ABCD + p * 0x12345) & 0xFFFFFFFF),
        (COOKIE, cookie),
        (s, (0xBF800000, 0x7FC01234, 0xFF800000)[p]),
    ):
        _write(pages, at, value.to_bytes(4, "little"))
    for offset in STRING_OFFSETS:
        _write(pages, s + offset, b"\0")
        _write(pages, s + offset + 16, bytes(4))
        _write(pages, s + offset + 20, (15).to_bytes(4, "little"))
    _write(pages, s + 0xCC, bytes(12))
    regs = {
        name: (0x12345678 + i * 0x11111111 + p * 0x1234) & 0xFFFFFFFF
        for i, name in enumerate(REGISTERS)
    }
    regs.update(ecx=d, esp=g)
    xmm = {
        name: int.from_bytes(
            bytes((i * 19 + j * 41 + p * 73) & 255 for j in range(16)), "little"
        )
        for i, name in enumerate(XMM)
    }
    return dict(
        pages=_pages(pages),
        registers=regs,
        xmm=xmm,
        return_address=RETURN,
        entry_flags=0x246,
    )


def _expected(vector, fixture):
    def run():
        _checked_vector(vector)
        _require(
            type(fixture) is dict
            and set(fixture) == FIXTURE_KEYS
            and _same_packet(fixture, _fixture(vector)),
            "empty record copy fixture differs",
        )
        result = model.apply(**fixture)
        _require(
            type(result) is dict
            and set(result) == EXPECTED_KEYS
            and all(type(k) is str for k in result),
            "empty record copy model schema differs",
        )
        g, d = fixture["registers"]["esp"], fixture["registers"]["ecx"]
        s = int.from_bytes(_read(fixture["pages"], g + 4), "little")
        cookie = int.from_bytes(_read(fixture["pages"], COOKIE), "little")
        seh = int.from_bytes(_read(fixture["pages"], 0), "little")
        wanted = dict(
            source_address=s,
            record_address=d,
            source_snapshot=_read(fixture["pages"], s, 308),
            registers=dict(
                fixture["registers"],
                eax=d,
                ecx=cookie ^ (g - 4),
                edx=s + 0xF8,
                esp=g + 8,
            ),
            xmm=dict(fixture["xmm"]),
            flags=0x85,
            flag_mask=0x8D5,
            df=0,
            endpoint=RETURN,
        )
        _require(
            _same_packet({k: result[k] for k in wanted}, wanted),
            "empty record copy model ABI or source differs",
        )
        memory = {page: bytearray(data) for page, data in fixture["pages"].items()}
        record = bytearray(_read(fixture["pages"], d, 308))
        written = set()
        for offset, width in FIELD_WIDTHS:
            record[offset : offset + width] = _read(fixture["pages"], s + offset, width)
            written.update(range(offset, offset + width))
        for offset in (0xCC, 0xD0, 0xD4):
            record[offset : offset + 4] = bytes(4)
            written.update(range(offset, offset + 4))
        for offset in STRING_OFFSETS:
            for at, width, value in (
                (offset, 1, 0),
                (offset + 16, 4, 0),
                (offset + 20, 4, 15),
            ):
                record[at : at + width] = value.to_bytes(width, "little")
                written.update(range(at, at + width))
        _require(
            len(written) == 183 and _same_packet(result["record_bytes"], bytes(record)),
            "empty record copy model field or padding differs",
        )
        _write(memory, d, record)
        _write(memory, 0, seh.to_bytes(4, "little"))
        final_slots = (
            (g - 4, fixture["registers"]["ebp"]),
            (g - 8, 7),
            (g - 12, 0x7B5837),
            (g - 16, seh),
            (g - 20, d),
            (g - 24, fixture["registers"]["esi"]),
            (g - 28, fixture["registers"]["edi"]),
            (g - 32, cookie ^ (g - 4)),
            (g - 36, 0xFFFFFFFF),
            (g - 40, 0),
            (g - 44, s + 0x118),
            (g - 48, 0x55BC93),
            (g - 52, g - 4),
            (g - 56, fixture["registers"]["ebx"]),
            (g - 60, d),
            (g - 64, s),
            (g - 68, d + 0xCC),
            (g - 72, s + 0xCC),
        )
        for address, value in final_slots:
            _write(memory, address, value.to_bytes(4, "little"))
        _require(
            _same_packet(result["pages"], _pages(memory)),
            "empty record copy model full pages differ",
        )
        _require(
            type(result["events"]) is list
            and len(result["events"]) == 315
            and _same_packet(result["trace_rvas"], [f"0x{pc:08x}" for pc in TRACE]),
            "empty record copy model path differs",
        )
        replay = {page: bytearray(data) for page, data in fixture["pages"].items()}
        for event in result["events"]:
            _require(
                type(event) is dict
                and set(event) == {"access", "address", "width", "value"}
                and all(type(k) is str for k in event)
                and type(event["access"]) is str
                and event["access"] in ("read", "write")
                and type(event["address"]) is int
                and 0 <= event["address"] <= 0xFFFFFFFF
                and type(event["width"]) is int
                and event["width"] in (1, 4)
                and type(event["value"]) is int
                and 0 <= event["value"] < 2 ** (8 * event["width"]),
                "empty record copy model event differs",
            )
            payload = event["value"].to_bytes(event["width"], "little")
            if event["access"] == "write":
                _write(replay, event["address"], payload)
            else:
                _require(
                    _read(replay, event["address"], event["width"]) == payload,
                    "empty record copy model read differs",
                )
        _require(
            _same_packet(result["pages"], _pages(replay)),
            "empty record copy model event pages differ",
        )
        _require(
            type(result["boundaries"]) is list and len(result["boundaries"]) == 20,
            "empty record copy model boundary count differs",
        )
        sequence = [
            ("string", name, index)
            for index in range(5)
            for name in ("entry", "return")
        ]
        sequence += [
            ("path", "entry", 0),
            ("reserve", "entry", 0),
            ("reserve", "return", 0),
            ("path", "return", 0),
        ]
        sequence += [
            ("string", name, index)
            for index in range(5, 8)
            for name in ("entry", "return")
        ]
        for row, (kind, name, index) in zip(result["boundaries"], sequence):
            endpoint = (
                (0x4080D0 if name == "entry" else STRING_RETURNS[index])
                if kind == "string"
                else (
                    (0x49A8E0 if name == "entry" else 0x55BBCA)
                    if kind == "path"
                    else (0x49AC40 if name == "entry" else 0x49A90C)
                )
            )
            flags, mask = (
                (0x85, 0x8D5)
                if kind == "string" or (kind == "path" and name == "entry")
                else (
                    (0x44, 0xC5)
                    if kind == "reserve" and name == "entry"
                    else (0x44, 0x8C5)
                )
            )
            _require(
                type(row) is dict
                and set(row) == BOUNDARY_KEYS
                and all(type(k) is str for k in row)
                and type(row["index"]) is int
                and _same_packet(
                    {
                        k: row[k]
                        for k in (
                            "kind",
                            "name",
                            "index",
                            "flags",
                            "flag_mask",
                            "df",
                            "endpoint",
                        )
                    },
                    dict(
                        kind=kind,
                        name=name,
                        index=index,
                        flags=flags,
                        flag_mask=mask,
                        df=0,
                        endpoint=endpoint,
                    ),
                )
                and type(row["registers"]) is dict
                and set(row["registers"]) == set(REGISTERS)
                and all(
                    type(k) is str and type(v) is int and 0 <= v <= 0xFFFFFFFF
                    for k, v in row["registers"].items()
                )
                and _same_packet(row["xmm"], fixture["xmm"])
                and type(row["pages"]) is dict
                and set(row["pages"]) == set(fixture["pages"])
                and all(
                    type(k) is int and type(v) is bytes and len(v) == 4096
                    for k, v in row["pages"].items()
                )
                and type(row["events"]) is list
                and _same_packet(row["events"], result["events"][: len(row["events"])]),
                "empty record copy model boundary schema differs",
            )
            expected_regs = dict(fixture["registers"], esi=d, edi=s, ebp=g - 4)
            if kind == "string":
                q, t = d + STRING_OFFSETS[index], s + STRING_OFFSETS[index]
                expected_regs.update(
                    eax=(t if index == 7 else q) if name == "entry" else q,
                    ecx=q if name == "entry" else 0,
                    edx=s + 0xF8 if index == 7 else t,
                    esp=g - 48 if name == "entry" else g - 32,
                )
            elif kind == "path":
                expected_regs.update(
                    eax=s + 0xCC if name == "entry" else d + 0xCC,
                    ecx=d + 0xCC,
                    edx=s + 0xA4,
                    esp=g - 40 if name == "entry" else g - 32,
                )
            else:
                expected_regs.update(
                    eax=0,
                    ecx=d + 0xCC,
                    edx=s + 0xA4,
                    esi=d + 0xCC,
                    edi=s + 0xCC,
                    ebp=g - 44,
                    esp=g - 60 if name == "entry" else g - 52,
                )
            _require(
                _same_packet(row["registers"], expected_regs),
                "empty record copy model boundary ABI differs",
            )
        return copy.deepcopy(result)

    return _normalize(run)


# Literal selected instruction occurrences from pinned decoded operand facts.
TRACE = (
    0x15B9B0,
    0x15B9B1,
    0x15B9B3,
    0x15B9B5,
    0x15B9BA,
    0x15B9C0,
    0x15B9C1,
    0x15B9C2,
    0x15B9C3,
    0x15B9C4,
    0x15B9C9,
    0x15B9CB,
    0x15B9CC,
    0x15B9CF,
    0x15B9D5,
    0x15B9D7,
    0x15B9DA,
    0x15B9DD,
    0x15B9E0,
    0x15B9E2,
    0x15B9E5,
    0x15B9E7,
    0x15B9EA,
    0x15B9ED,
    0x15B9F0,
    0x15B9F3,
    0x15B9F6,
    0x15B9F9,
    0x15B9FC,
    0x15B9FF,
    0x15BA03,
    0x15BA06,
    0x15BA09,
    0x15BA0C,
    0x15BA0F,
    0x15BA12,
    0x15BA15,
    0x15BA18,
    0x15BA1B,
    0x15BA1E,
    0x15BA21,
    0x15BA24,
    0x15BA27,
    0x15BA2A,
    0x15BA2E,
    0x15BA31,
    0x15BA35,
    0x15BA38,
    0x15BA3B,
    0x15BA3E,
    0x15BA45,
    0x15BA4C,
    0x15BA50,
    0x15BA56,
    0x15BA58,
    0x15BA5A,
    0x15BA5C,
    0x15BA5D,
    0x15BA60,
    0x80D0,
    0x80D1,
    0x80D3,
    0x80D4,
    0x80D7,
    0x80D8,
    0x80DA,
    0x80DD,
    0x80DE,
    0x80E1,
    0x80E3,
    0x80E9,
    0x80EC,
    0x80EE,
    0x80F0,
    0x80F3,
    0x80F5,
    0x813E,
    0x8141,
    0x8147,
    0x814A,
    0x8170,
    0x8172,
    0x8174,
    0x8178,
    0x817B,
    0x818B,
    0x818D,
    0x818E,
    0x818F,
    0x8190,
    0x8193,
    0x8194,
    0x15BA65,
    0x15BA68,
    0x15BA6F,
    0x15BA76,
    0x15BA79,
    0x15BA80,
    0x15BA84,
    0x15BA8A,
    0x15BA8C,
    0x15BA8E,
    0x15BA90,
    0x15BA91,
    0x15BA94,
    0x80D0,
    0x80D1,
    0x80D3,
    0x80D4,
    0x80D7,
    0x80D8,
    0x80DA,
    0x80DD,
    0x80DE,
    0x80E1,
    0x80E3,
    0x80E9,
    0x80EC,
    0x80EE,
    0x80F0,
    0x80F3,
    0x80F5,
    0x813E,
    0x8141,
    0x8147,
    0x814A,
    0x8170,
    0x8172,
    0x8174,
    0x8178,
    0x817B,
    0x818B,
    0x818D,
    0x818E,
    0x818F,
    0x8190,
    0x8193,
    0x8194,
    0x15BA99,
    0x15BA9C,
    0x15BAA0,
    0x15BAA7,
    0x15BAAA,
    0x15BAB1,
    0x15BAB5,
    0x15BABB,
    0x15BABD,
    0x15BABF,
    0x15BAC1,
    0x15BAC2,
    0x15BAC5,
    0x80D0,
    0x80D1,
    0x80D3,
    0x80D4,
    0x80D7,
    0x80D8,
    0x80DA,
    0x80DD,
    0x80DE,
    0x80E1,
    0x80E3,
    0x80E9,
    0x80EC,
    0x80EE,
    0x80F0,
    0x80F3,
    0x80F5,
    0x813E,
    0x8141,
    0x8147,
    0x814A,
    0x8170,
    0x8172,
    0x8174,
    0x8178,
    0x817B,
    0x818B,
    0x818D,
    0x818E,
    0x818F,
    0x8190,
    0x8193,
    0x8194,
    0x15BACA,
    0x15BAD0,
    0x15BAD4,
    0x15BADB,
    0x15BAE1,
    0x15BAE8,
    0x15BAEC,
    0x15BAF2,
    0x15BAF4,
    0x15BAF6,
    0x15BAF8,
    0x15BAF9,
    0x15BAFC,
    0x80D0,
    0x80D1,
    0x80D3,
    0x80D4,
    0x80D7,
    0x80D8,
    0x80DA,
    0x80DD,
    0x80DE,
    0x80E1,
    0x80E3,
    0x80E9,
    0x80EC,
    0x80EE,
    0x80F0,
    0x80F3,
    0x80F5,
    0x813E,
    0x8141,
    0x8147,
    0x814A,
    0x8170,
    0x8172,
    0x8174,
    0x8178,
    0x817B,
    0x818B,
    0x818D,
    0x818E,
    0x818F,
    0x8190,
    0x8193,
    0x8194,
    0x15BB01,
    0x15BB05,
    0x15BB0B,
    0x15BB11,
    0x15BB17,
    0x15BB1D,
    0x15BB23,
    0x15BB29,
    0x15BB2F,
    0x15BB35,
    0x15BB3C,
    0x15BB43,
    0x15BB47,
    0x15BB4D,
    0x15BB4F,
    0x15BB51,
    0x15BB53,
    0x15BB54,
    0x15BB57,
    0x80D0,
    0x80D1,
    0x80D3,
    0x80D4,
    0x80D7,
    0x80D8,
    0x80DA,
    0x80DD,
    0x80DE,
    0x80E1,
    0x80E3,
    0x80E9,
    0x80EC,
    0x80EE,
    0x80F0,
    0x80F3,
    0x80F5,
    0x813E,
    0x8141,
    0x8147,
    0x814A,
    0x8170,
    0x8172,
    0x8174,
    0x8178,
    0x817B,
    0x818B,
    0x818D,
    0x818E,
    0x818F,
    0x8190,
    0x8193,
    0x8194,
    0x15BB5C,
    0x15BB60,
    0x15BB66,
    0x15BB6C,
    0x15BB72,
    0x15BB78,
    0x15BB7E,
    0x15BB85,
    0x15BB8B,
    0x15BB92,
    0x15BB98,
    0x15BB9F,
    0x15BBA5,
    0x15BBAC,
    0x15BBB2,
    0x15BBB8,
    0x15BBBE,
    0x15BBC4,
    0x15BBC5,
    0x9A8E0,
    0x9A8E1,
    0x9A8E3,
    0x9A8E4,
    0x9A8E6,
    0x9A8E7,
    0x9A8EA,
    0x9A8F0,
    0x9A8F7,
    0x9A8FE,
    0x9A901,
    0x9A903,
    0x9A906,
    0x9A907,
    0x9AC40,
    0x9AC41,
    0x9AC43,
    0x9AC44,
    0x9AC46,
    0x9AC47,
    0x9AC4A,
    0x9AC50,
    0x9AC57,
    0x9AC5E,
    0x9AC60,
    0x9AC62,
    0x9AC63,
    0x9AC65,
    0x9AC66,
    0x9AC67,
    0x9A90C,
    0x9A90E,
    0x9A927,
    0x9A928,
    0x9A92A,
    0x9A92B,
    0x9A92C,
    0x15BBCA,
    0x15BBCE,
    0x15BBD4,
    0x15BBDA,
    0x15BBE0,
    0x15BBE6,
    0x15BBEC,
    0x15BBF2,
    0x15BBF9,
    0x15BC00,
    0x15BC04,
    0x15BC0A,
    0x15BC0C,
    0x15BC0E,
    0x15BC10,
    0x15BC11,
    0x15BC14,
    0x80D0,
    0x80D1,
    0x80D3,
    0x80D4,
    0x80D7,
    0x80D8,
    0x80DA,
    0x80DD,
    0x80DE,
    0x80E1,
    0x80E3,
    0x80E9,
    0x80EC,
    0x80EE,
    0x80F0,
    0x80F3,
    0x80F5,
    0x813E,
    0x8141,
    0x8147,
    0x814A,
    0x8170,
    0x8172,
    0x8174,
    0x8178,
    0x817B,
    0x818B,
    0x818D,
    0x818E,
    0x818F,
    0x8190,
    0x8193,
    0x8194,
    0x15BC19,
    0x15BC1F,
    0x15BC23,
    0x15BC2A,
    0x15BC30,
    0x15BC37,
    0x15BC3B,
    0x15BC41,
    0x15BC43,
    0x15BC45,
    0x15BC47,
    0x15BC48,
    0x15BC4B,
    0x80D0,
    0x80D1,
    0x80D3,
    0x80D4,
    0x80D7,
    0x80D8,
    0x80DA,
    0x80DD,
    0x80DE,
    0x80E1,
    0x80E3,
    0x80E9,
    0x80EC,
    0x80EE,
    0x80F0,
    0x80F3,
    0x80F5,
    0x813E,
    0x8141,
    0x8147,
    0x814A,
    0x8170,
    0x8172,
    0x8174,
    0x8178,
    0x817B,
    0x818B,
    0x818D,
    0x818E,
    0x818F,
    0x8190,
    0x8193,
    0x8194,
    0x15BC50,
    0x15BC54,
    0x15BC5A,
    0x15BC60,
    0x15BC66,
    0x15BC6C,
    0x15BC72,
    0x15BC78,
    0x15BC7A,
    0x15BC7C,
    0x15BC83,
    0x15BC8A,
    0x15BC8B,
    0x15BC8E,
    0x80D0,
    0x80D1,
    0x80D3,
    0x80D4,
    0x80D7,
    0x80D8,
    0x80DA,
    0x80DD,
    0x80DE,
    0x80E1,
    0x80E3,
    0x80E9,
    0x80EC,
    0x80EE,
    0x80F0,
    0x80F3,
    0x80F5,
    0x813E,
    0x8141,
    0x8147,
    0x814A,
    0x8170,
    0x8172,
    0x8174,
    0x8178,
    0x817B,
    0x818B,
    0x818D,
    0x818E,
    0x818F,
    0x8190,
    0x8193,
    0x8194,
    0x15BC93,
    0x15BC99,
    0x15BC9F,
    0x15BCA1,
    0x15BCA4,
    0x15BCAB,
    0x15BCAC,
    0x15BCAD,
    0x15BCAE,
    0x15BCB0,
    0x15BCB1,
)


def _preflight(sources):
    def run():
        _require(
            type(sources) is dict and set(sources) == set(SOURCE_PINS),
            "empty record copy source partition differs",
        )
        common._validate_json_tree(sources, "sources")
        identities = {
            key: common._source_identity(sources[key], *pin, key)
            for key, pin in SOURCE_PINS.items()
        }
        identity = sources["program_facts"]["identity"]
        _require(
            identity["executable_sha256"] == EXE_SHA256
            and all(
                _same_packet(identity, sources[key]["build_identity"])
                for key in SOURCE_PINS
                if key != "program_facts"
            ),
            "empty record copy source build differs",
        )
        atlas = {
            int(row["entry_rva"], 16): row
            for row in sources["program_facts"]["functions"]
        }
        _require(
            len(atlas) == len(sources["program_facts"]["functions"]),
            "empty record copy duplicate atlas entry",
        )
        for start, (size, digest) in BODY_PINS.items():
            row = atlas[start]
            _require(
                type(row["body_size"]) is int
                and row["body_size"] == size
                and row["body_sha256"] == digest
                and row["ranges"] == [dict(start_rva=f"0x{start:08x}", size=size)],
                "empty record copy atlas body differs",
            )
        return identities

    return _normalize(run)


def _checked_code_packet(codes, points):
    def run():
        _require(
            type(codes) is dict
            and all(type(k) is int for k in codes)
            and set(codes) == set(BODY_PINS)
            and type(points) is list
            and _canonical_sha256(points) == POINTS_SHA256,
            "empty record copy direct code identity differs",
        )
        _require(
            points == sorted(points, key=lambda p: int(p["rva"], 16)),
            "empty record copy direct point order differs",
        )
        allowed = {}
        for start, size in BODIES:
            _require(
                type(codes[start]) is bytes
                and len(codes[start]) == size
                and hashlib.sha256(codes[start]).hexdigest() == BODY_PINS[start][1],
                "empty record copy direct body differs",
            )
            cursor = start
            for point in (
                row for row in points if start <= int(row["rva"], 16) < start + size
            ):
                _require(
                    type(point) is dict
                    and set(point) == {"rva", "size", "sha256"}
                    and all(type(k) is str for k in point)
                    and type(point["rva"]) is str
                    and type(point["size"]) is int
                    and point["size"] > 0
                    and type(point["sha256"]) is str,
                    "empty record copy direct point differs",
                )
                pc = int(point["rva"], 16)
                _require(
                    point["rva"] == f"0x{pc:08x}"
                    and pc == cursor
                    and pc + point["size"] <= start + size
                    and hashlib.sha256(
                        codes[start][pc - start : pc - start + point["size"]]
                    ).hexdigest()
                    == point["sha256"],
                    "empty record copy direct bytes differ",
                )
                allowed[pc] = point
                cursor += point["size"]
            _require(cursor == start + size, "empty record copy direct extent differs")
        _require(
            len(allowed) == len(points) == 386,
            "empty record copy direct partition differs",
        )
        return allowed

    return _normalize(run)


def _load_code(data, image, sources):
    def run():
        _preflight(sources)
        _require(
            type(data) is bytes
            and hashlib.sha256(data).hexdigest() == EXE_SHA256
            and image.image_base == BASE,
            "empty record copy executable differs",
        )
        codes = {}
        points = []
        for start, size in BODIES:
            rows = common._decode_body(data, image, sources["program_facts"], start)
            codes[start] = b"".join(bytes(row.bytes) for row in rows)
            points.extend(common._point(row) for row in rows)
        points.sort(key=lambda p: int(p["rva"], 16))
        _checked_code_packet(codes, points)
        return codes, points

    return _normalize(run)


CONTROL_ROLES = (
    "outer_entry",
    "string_entry",
    "string_return",
    "path_entry",
    "path_return",
    "reserve_entry",
    "reserve_return",
)
CONTROLS = {
    **{
        role + "_" + kind: "empty record copy " + role.replace("_", " ") + " differs"
        for role in CONTROL_ROLES
        for kind in ("gpr", "xmm", "flags", "df", "page")
    },
    **{
        name: "empty record copy ordered memory differs"
        for name in ("caller_source", "source_size", "destination_capacity")
    },
    **{
        name: "empty record copy final pages differ"
        for name in (
            "field",
            "padding",
            "source",
            "source_padding",
            "source_capacity",
            "source_terminator",
            "stack_ancestor",
            "stack_padding",
            "seh",
            "cookie",
            "random_padding",
        )
    },
    **{
        name: "empty record copy final ABI differs"
        for name in (
            "final_gpr",
            "final_edx",
            "final_xmm",
            "final_flags",
            "final_df",
            "final_endpoint",
        )
    },
    "missing_read_record": "empty record copy final events differ",
    "restored_write_record": "empty record copy final events differ",
    "trace_record": "empty record copy final native path differs",
}


def _run_case(codes, points, vector, negative=None, *, capture=None):
    _require(
        negative is None or type(negative) is str and negative in CONTROLS,
        "invalid empty record copy control",
    )
    fixture = _fixture(vector)
    wanted = _expected(vector, fixture)
    allowed = _checked_code_packet(codes, points)
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "empty record copy reviewed Unicorn required")
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    machine.ctl_set_cpu_model(CPU_MODEL)
    _require(machine.ctl_get_cpu_model() == CPU_MODEL, "empty record copy CPU differs")
    g, d = fixture["registers"]["esp"], fixture["registers"]["ecx"]
    s = wanted["source_address"]
    stop = fixture["return_address"]
    code_pages = {
        (BASE + pc) & ~4095
        for start, size in BODIES
        for pc in range(start, start + size)
    } | {stop & ~4095}
    _require(
        not code_pages.intersection(fixture["pages"]),
        "empty record copy mappings overlap",
    )
    for page in sorted(code_pages):
        machine.mem_map(page, 4096)
        machine.mem_write(page, bytes([0xCC]) * 4096)
    for page, payload in fixture["pages"].items():
        machine.mem_map(page, 4096)
        machine.mem_write(page, payload)
    for start, payload in codes.items():
        machine.mem_write(BASE + start, payload)
    ids = {name: getattr(x, "UC_X86_REG_" + name.upper()) for name in REGISTERS}
    xmm_ids = {name: getattr(x, "UC_X86_REG_" + name.upper()) for name in XMM}
    for name, value in fixture["registers"].items():
        machine.reg_write(ids[name], value)
    for name, value in fixture["xmm"].items():
        machine.reg_write(xmm_ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, fixture["entry_flags"])
    events = []
    trace = []
    boundaries = []
    cursor = 0
    outer = dict(
        kind="outer",
        name="entry",
        index=0,
        registers=dict(fixture["registers"]),
        xmm=dict(fixture["xmm"]),
        pages=dict(fixture["pages"]),
        events=[],
        flags=0x44,
        flag_mask=0x8D5,
        df=0,
        endpoint=0x55B9B0,
    )

    def flip(at):
        machine.mem_write(at, bytes([machine.mem_read(at, 1)[0] ^ 1]))

    def check_boundary(state, role):
        targeted = state["kind"] != "string" or state["index"] == 7
        if targeted:
            if negative == role + "_gpr":
                machine.reg_write(ids["edx"], machine.reg_read(ids["edx"]) ^ 1)
            if negative == role + "_xmm":
                machine.reg_write(
                    xmm_ids["xmm7"], machine.reg_read(xmm_ids["xmm7"]) ^ 1
                )
            if negative in (role + "_flags", role + "_df"):
                machine.reg_write(
                    x.UC_X86_REG_EFLAGS,
                    machine.reg_read(x.UC_X86_REG_EFLAGS)
                    ^ (1 if negative == role + "_flags" else 0x400),
                )
            if negative == role + "_page":
                flip(d + 0x15)
        raw = machine.reg_read(x.UC_X86_REG_EFLAGS)
        actual = dict(
            kind=state["kind"],
            name=state["name"],
            index=state["index"],
            registers={name: machine.reg_read(reg) for name, reg in ids.items()},
            xmm={name: machine.reg_read(reg) for name, reg in xmm_ids.items()},
            pages={
                page: bytes(machine.mem_read(page, 4096)) for page in fixture["pages"]
            },
            events=copy.deepcopy(events),
            flags=raw & state["flag_mask"],
            flag_mask=state["flag_mask"],
            df=(raw >> 10) & 1,
            endpoint=machine.reg_read(x.UC_X86_REG_EIP),
        )
        _require(
            _same_packet(actual, state) and (role != "outer_entry" or raw == 0x246),
            "empty record copy " + role.replace("_", " ") + " differs",
        )
        boundaries.append(
            dict(
                kind=state["kind"],
                name=state["name"],
                index=state["index"],
                registers=actual["registers"],
                xmm=actual["xmm"],
                eflags=raw,
                flags=actual["flags"],
                flag_mask=state["flag_mask"],
                df=actual["df"],
                endpoint=actual["endpoint"],
                pages_sha256=_page_hashes(actual["pages"]),
                events_sha256=_canonical_sha256(events),
            )
        )

    def on_code(m, address, size, user):
        nonlocal cursor
        if address == stop:
            m.emu_stop()
            return
        pc = address - BASE
        _require(
            pc in allowed and size == allowed[pc]["size"],
            "empty record copy escaped selected code",
        )
        if pc == 0x15B9B0:
            _require(
                not trace and not boundaries, "empty record copy repeated outer entry"
            )
            check_boundary(outer, "outer_entry")
        if cursor < 20:
            state = wanted["boundaries"][cursor]
            if address == state["endpoint"]:
                check_boundary(state, state["kind"] + "_" + state["name"])
                cursor += 1
        if negative == "caller_source" and pc == 0x15B9DA:
            flip(g + 4)
        if negative == "source_size" and pc == 0x80DE and cursor == 1:
            flip(s + 0x38 + 16)
        if negative == "destination_capacity" and pc == 0x15BA4C:
            flip(d + 0x38 + 20)
        trace.append(f"0x{pc:08x}")
        _require(
            trace == wanted["trace_rvas"][: len(trace)],
            "empty record copy native path differs",
        )

    def on_memory(m, access, address, width, value, user):
        _require(width in (1, 4), "empty record copy access width differs")
        writing = access == uc.UC_MEM_WRITE
        row = dict(
            access="write" if writing else "read",
            address=address,
            width=width,
            value=(
                value & ((1 << (8 * width)) - 1)
                if writing
                else int.from_bytes(m.mem_read(address, width), "little")
            ),
        )
        _require(
            len(events) < 315 and _same_packet(row, wanted["events"][len(events)]),
            "empty record copy ordered memory differs",
        )
        events.append(row)

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    machine.emu_start(BASE + 0x15B9B0, 0, count=10000)
    corrupt = dict(
        field=d + 0x34,
        padding=d + 0x15,
        source=s,
        source_padding=s + 0x15,
        source_capacity=s + 0x38 + 20,
        source_terminator=s + 0x38,
        stack_ancestor=g + 8,
        stack_padding=g - 76,
        seh=0,
        cookie=COOKIE,
        random_padding=DEST_PAGE + 1,
    )
    if negative in corrupt:
        flip(corrupt[negative])
    if negative in ("final_gpr", "final_edx"):
        name = "eax" if negative == "final_gpr" else "edx"
        machine.reg_write(ids[name], machine.reg_read(ids[name]) ^ 1)
    if negative == "final_xmm":
        machine.reg_write(xmm_ids["xmm0"], machine.reg_read(xmm_ids["xmm0"]) ^ 1)
    if negative in ("final_flags", "final_df"):
        machine.reg_write(
            x.UC_X86_REG_EFLAGS,
            machine.reg_read(x.UC_X86_REG_EFLAGS)
            ^ (1 if negative == "final_flags" else 0x400),
        )
    if negative == "final_endpoint":
        machine.reg_write(x.UC_X86_REG_EIP, stop + 1)
    if negative == "missing_read_record":
        events.pop()
    if negative == "restored_write_record":
        events.extend(
            [
                dict(access="write", address=s + 0x15, width=1, value=0),
                dict(
                    access="write",
                    address=s + 0x15,
                    width=1,
                    value=wanted["source_snapshot"][0x15],
                ),
            ]
        )
    if negative == "trace_record":
        trace.append("0x0009ac6a")
    raw = machine.reg_read(x.UC_X86_REG_EFLAGS)
    regs = {name: machine.reg_read(reg) for name, reg in ids.items()}
    xmm = {name: machine.reg_read(reg) for name, reg in xmm_ids.items()}
    pages = {page: bytes(machine.mem_read(page, 4096)) for page in fixture["pages"]}
    _require(
        _same_packet(regs, wanted["registers"])
        and _same_packet(xmm, wanted["xmm"])
        and raw & 0x8D5 == 0x85
        and raw & 0x400 == 0
        and machine.reg_read(x.UC_X86_REG_EIP) == stop,
        "empty record copy final ABI differs",
    )
    _require(
        _same_packet(pages, wanted["pages"]), "empty record copy final pages differ"
    )
    _require(
        _same_packet(events, wanted["events"]), "empty record copy final events differ"
    )
    _require(
        _same_packet(trace, wanted["trace_rvas"]),
        "empty record copy final native path differs",
    )
    _require(
        cursor == 20 and len(boundaries) == 21, "empty record copy missing boundaries"
    )
    result = dict(
        vector=dict(vector),
        registers=regs,
        xmm=xmm,
        eflags=raw,
        flags=raw & 0x8D5,
        flag_mask=0x8D5,
        df=0,
        endpoint=stop,
        trace_rvas=trace,
        events_sha256=_canonical_sha256(events),
        pages_sha256=_page_hashes(pages),
        memory_event_count=len(events),
        boundaries=boundaries,
    )
    if capture is not None:
        capture(machine, dict(ids), copy.deepcopy(wanted), copy.deepcopy(fixture))
    return result


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _normalize(lambda: common._load_executable(Path(executable)))
    codes, points = _load_code(data, image, sources)
    observations = [_run_case(codes, points, vector) for vector in vectors()]
    controls = []
    for name, reason in CONTROLS.items():
        try:
            _run_case(codes, points, vectors()[-1], name)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "empty record copy incidental control: " + name + ": " + str(exc),
            )
            controls.append(dict(name=name, rejected=True, reason=reason))
        else:
            raise ConformanceError("empty record copy control survived: " + name)
    executed = sorted({pc for row in observations for pc in row["trace_rvas"]})
    _require(
        set(executed) == {f"0x{pc:08x}" for pc in TRACE},
        "empty record copy native coverage differs",
    )
    n = len(observations)
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=copy.deepcopy(sources["program_facts"]["identity"]),
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{start:08x}",
                    exclusive_end_rva=f"0x{start+size:08x}",
                    sha256=hashlib.sha256(codes[start]).hexdigest(),
                )
                for start, size in BODIES
            ],
            points=points,
        ),
        vectors=vectors(),
        engine=dict(
            name="Unicorn",
            version="2.1.4",
            architecture="x86_32",
            cpu_model=dict(id=CPU_MODEL, name="UC_CPU_X86_HASWELL"),
        ),
        executed_rvas=executed,
        observations_sha256=_canonical_sha256(observations),
        negative_controls=controls,
        summary=dict(
            cases=n,
            loaded_sites=len(points),
            loaded_bytes=sum(map(len, codes.values())),
            executed_sites=len(executed),
            native_instructions=sum(len(row["trace_rvas"]) for row in observations),
            memory_events=sum(row["memory_event_count"] for row in observations),
            native_boundary_snapshots=sum(
                len(row["boundaries"]) for row in observations
            ),
            empty_string_calls=8 * n,
            empty_path_calls=n,
            zero_reserve_calls=n,
            source_bytes_preserved=308 * n,
            record_bytes=308 * n,
            record_written_bytes=183 * n,
            record_padding_bytes_preserved=125 * n,
            copied_scalar_bytes=99 * n,
            empty_string_field_bytes=72 * n,
            initialized_empty_path_bytes=12 * n,
            xmm_preserved_cases=n,
            allocation_requests=0,
            free_requests=0,
            scalar_clone_calls=0,
            wide_reads=0,
            wide_writes=0,
            api_responses=0,
            cookie_checker_calls=0,
            opaque_instructions=0,
            controls=len(controls),
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Finite continuous normal movement record copy with eight empty inline strings and an empty source path",
            premises=[
                "Exactly 48 synthetic alignment and profile recipes with positive disjoint complete 308-byte source and destination records crossing page boundaries",
                "One CPU19 Unicorn executes owner eight empty-string assignments empty path clone and zero-count reserve continuously with no delegated native helper or supplied API response",
                "All eight source inline strings have size zero capacity fifteen and first byte zero; source path begin end and capacity triple is zero; these are premises even where selected code does not read them",
                "Complete model packet is checked against separate destination183 source308 full pages saved stack and final ABI equations and literal492 instruction trace before execution",
                "Model event replay checks typed315 access records and page consistency; actual native online checks and independent test oracles establish the complete ordered accesses",
                "All eight general and XMM registers full pages ordered event prefixes defined flags DF and PC are checked at outer entry and twenty sequential kind name and index helper boundaries",
                "FS base zero with source SEH and cookie slots supplied; saved SEH and cached cookie restore normally with no cookie checker or failure-handler execution",
                "Destination scalar fields copy arbitrary source bit patterns; initialized path and empty string fields are written while all125 destination padding bytes and complete source308 are preserved",
                "Architecturally defined flag masks and DF zero are distinct from recorded raw finite VM EFLAGS",
            ],
            not_claimed=[
                "Allocator API execution ownership unmapping destruction exception unwind failure handler cookie validation operating-system or hardware execution",
                "Nonempty strings or paths record assignment vector append receiver growth AddMove greater than one AddCharge gameplay or Lua reachability",
                "Model event replay count and trace alone reject every coordinated same-count event forgery before execution",
                "Missing restored-write and trace record mutations establish execution of represented writes or instructions",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "empty record copy executable changed",
    )
    common._assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    def run():
        common._validate_json_tree(evidence, "evidence")
        identities = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256
            and _same_packet(evidence["source_receipts"], identities)
            and _same_packet(evidence["vectors"], vectors()),
            "sealed empty record copy receipt differs",
        )
        common._assert_publication_safe(evidence)
        return dict(
            status="structurally_verified",
            evidence_sha256=SEALED_SHA256,
            summary=copy.deepcopy(evidence["summary"]),
        )

    return _normalize(run)


def build_conformance(executable, sources):
    def run():
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_conformance(executable, evidence, sources):
    def run():
        validate_structure(evidence, sources)
        _require(
            _same_packet(_build_unsealed(executable, sources), evidence),
            "empty record copy native rebuild differs",
        )
        return dict(
            status="verified",
            evidence_sha256=SEALED_SHA256,
            summary=copy.deepcopy(evidence["summary"]),
        )

    return _normalize(run)


def encode_conformance(value):
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
