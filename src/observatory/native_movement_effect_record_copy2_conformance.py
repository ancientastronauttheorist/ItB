"""Finite continuous normal record copy with eight empty strings and count-two path.

One successful ordinary allocation response is supplied within one machine.
This proves synthetic pages and normal state, not gameplay or ownership.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from src.observatory import native_assertion_helper_fill_conformance as common
from src.observatory import native_movement_effect_record_copy2_semantics as model
from src.observatory import native_vector_allocation_conformance as allocator
from src.observatory import native_movement_path_scalar_clone2_semantics as scalar

BASE, EXE_SHA256 = common.BASE, common.EXE_SHA256
ANALYSIS_KIND = "pe_native_movement_effect_record_copy2_conformance"
SEALED_SHA256 = "594b01e901b028f23bc8a75857d9ddf775b481b22285bdaca74fe301753f5489"
POINTS_SHA256 = "4153ee13abbc8b63b43b1d04d1f5bc64b57ec7e28ba8d7e262f2b420c0714a5d"
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
DATA, HEAP_GLOBAL, ALLOC_IAT, HEAP, IMPORT = (
    0x06000000,
    0x008B7634,
    0x007D6220,
    0x12345678,
    0x05000000,
)
BODY_PINS = {
    0x15B9B0: (772, "3846fdb1ca2ebc1b4b6e83a64994f82d4907938345ff0d856c9bbea690957fc6"),
    0x80D0: (288, "062ae02111f4145fc3b614c93355bc20d6ae59544117d4c8bdcff4d82c488333"),
    0x9A8E0: (79, "4359ecaf051506bce97afe182b66c453ca8d13ac4091d72a810f9df43d14d2e0"),
    0x9AC40: (87, "29a0428ed018a85e4e0a76f283f10040cf9e084f49bee5706b58766b570cb9d1"),
    0x8ABA0: (43, "92494ea2dfd86d06ce373c9837f55d42e6c62746bd9c2c3c26d2a8af6abe938b"),
    0x8A920: (91, "e13e3be9b5e53d78d61aaaacc91b9c7c3183b77ef1f005bd2010bc1aa9b9830e"),
    0x3574DB: (51, "452b4c981b0a2567c6f4fc35b20076deca45a6b3509707358212028d21db5bfa"),
    0x379F52: (11, "831e215b24984219b6d6d7ce812127a420a48782704f0fef1630b1b8050cabbd"),
    0x38942B: (78, "d97ee587f29bfdaf154ca653059e883b67b56713a5d96643356a4edf6e3edde8"),
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
FIXTURE_KEYS = {
    "pages",
    "registers",
    "xmm",
    "return_address",
    "entry_flags",
    "allocation_result",
}
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
    "path_packet",
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
        "outside fixed record copy2 domain",
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
                DATA,
                DATA + 4096,
                DATA + 8192,
                DATA + 12288,
                HEAP_GLOBAL & ~4095,
                ALLOC_IAT & ~4095,
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
        (HEAP_GLOBAL, HEAP),
        (ALLOC_IAT, IMPORT),
        (s + 0xCC, DATA + 0x2FF9 + a),
        (s + 0xD0, DATA + 0x3009 + a),
        (s + 0xD4, (0, 0xFFFFFFFF, 0xDEADBEEF)[p]),
    ):
        _write(pages, at, value.to_bytes(4, "little"))
    for offset in STRING_OFFSETS:
        _write(pages, s + offset, b"\0")
        _write(pages, s + offset + 16, bytes(4))
        _write(pages, s + offset + 20, (15).to_bytes(4, "little"))
    for index, word in enumerate((0xD15C0016, 0xFFFFFFFF, 0x80000000, 0x8765DD16)):
        _write(
            pages,
            DATA + 0x2FF9 + a + index * 4,
            (word ^ (p * 0x07654321)).to_bytes(4, "little"),
        )
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
        allocation_result=DATA + 0x1103 + a,
    )


def _prefix_pages(fixture):
    """Independent last-writer law just before the installed path CALL."""
    memory = {page: bytearray(data) for page, data in fixture["pages"].items()}
    g = fixture["registers"]["esp"]
    d = fixture["registers"]["ecx"]
    s = int.from_bytes(_read(fixture["pages"], g + 4), "little")
    seh = int.from_bytes(_read(fixture["pages"], 0), "little")
    cookie = int.from_bytes(_read(fixture["pages"], COOKIE), "little")
    for offset, width in FIELD_WIDTHS:
        if offset <= 0xC8:
            _write(memory, d + offset, _read(fixture["pages"], s + offset, width))
    for offset in STRING_OFFSETS[:5]:
        _write(memory, d + offset, b"\0")
        _write(memory, d + offset + 16, bytes(4))
        _write(memory, d + offset + 20, (15).to_bytes(4, "little"))
    values = (
        fixture["registers"]["ebp"],
        4,
        0x007B5837,
        seh,
        d,
        fixture["registers"]["esi"],
        fixture["registers"]["edi"],
        cookie ^ (g - 4),
        s + 0xCC,
        0x55BBCA,
        s + 0xA4,
        0x55BB5C,
        g - 4,
        fixture["registers"]["ebx"],
        d,
        s,
    )
    for index, value in enumerate(values, 1):
        _write(memory, g - 4 * index, value.to_bytes(4, "little"))
    _write(memory, 0, (g - 16).to_bytes(4, "little"))
    return _pages(memory), dict(
        fixture["registers"],
        eax=s + 0xCC,
        ecx=d + 0xCC,
        edx=s + 0xA4,
        esi=d,
        edi=s,
        ebp=g - 4,
        esp=g - 40,
    )


def _expected(vector, fixture):
    def run():
        _checked_vector(vector)
        _require(
            type(fixture) is dict
            and set(fixture) == FIXTURE_KEYS
            and _same_packet(fixture, _fixture(vector)),
            "record copy2 fixture differs",
        )
        result = model.apply(**fixture)
        _require(
            type(result) is dict
            and set(result) == EXPECTED_KEYS
            and all(type(k) is str for k in result),
            "record copy2 model schema differs",
        )
        g, d = fixture["registers"]["esp"], fixture["registers"]["ecx"]
        s = int.from_bytes(_read(fixture["pages"], g + 4), "little")
        o = int.from_bytes(_read(fixture["pages"], s + 0xCC), "little")
        allocated = fixture["allocation_result"]
        seh = int.from_bytes(_read(fixture["pages"], 0), "little")
        cookie = int.from_bytes(_read(fixture["pages"], COOKIE), "little")
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
            "record copy2 model ABI or source differs",
        )
        prefix_pages, prefix_regs = _prefix_pages(fixture)
        child = _path_packet_law(
            pages=prefix_pages,
            registers=prefix_regs,
            xmm=dict(fixture["xmm"]),
            return_address=0x55BBCA,
            entry_flags=0x287,
            allocation_result=allocated,
        )
        _require(
            _same_packet(result["path_packet"], child),
            "record copy2 full path packet differs",
        )
        record = bytearray(_read(fixture["pages"], d, 308))
        written = set()
        for offset, width in FIELD_WIDTHS:
            record[offset : offset + width] = _read(fixture["pages"], s + offset, width)
            written.update(range(offset, offset + width))
        for offset, value in (
            (0xCC, allocated),
            (0xD0, allocated + 16),
            (0xD4, allocated + 16),
        ):
            record[offset : offset + 4] = value.to_bytes(4, "little")
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
            "record copy2 model field or padding differs",
        )
        memory = {page: bytearray(data) for page, data in fixture["pages"].items()}
        _write(memory, d, record)
        _write(memory, allocated, _read(fixture["pages"], o, 16))
        _write(memory, 0, seh.to_bytes(4, "little"))
        values = (
            fixture["registers"]["ebp"],
            7,
            0x007B5837,
            seh,
            d,
            fixture["registers"]["esi"],
            fixture["registers"]["edi"],
            cookie ^ (g - 4),
            0xFFFFFFFF,
            0,
            s + 0x118,
            0x55BC93,
            g - 4,
            fixture["registers"]["ebx"],
            d,
            s,
            allocated,
            0x49A921,
            g - 44,
            d + 0xCC,
            g - 64,
            16,
            0x48A968,
            g - 84,
            16,
            0x757507,
            g - 96,
            d + 0xCC,
            16,
            0,
            HEAP,
            0x789463,
        )
        for index, value in enumerate(values, 1):
            _write(memory, g - 4 * index, value.to_bytes(4, "little"))
        _require(
            _same_packet(result["pages"], _pages(memory)),
            "record copy2 model full pages differ",
        )
        _require(
            type(result["events"]) is list
            and len(result["events"]) == 372
            and _same_packet(result["trace_rvas"], [f"0x{pc:08x}" for pc in TRACE]),
            "record copy2 model path differs",
        )
        replay = {page: bytearray(data) for page, data in fixture["pages"].items()}
        snapshots = {}
        prefixes = (
            51,
            68,
            77,
            94,
            103,
            120,
            129,
            146,
            161,
            178,
            195,
            206,
            215,
            242,
            250,
            259,
            273,
            291,
            308,
            317,
            334,
            346,
            363,
        )
        for index, event in enumerate(result["events"], 1):
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
                "record copy2 model event differs",
            )
            payload = event["value"].to_bytes(event["width"], "little")
            if event["access"] == "write":
                _write(replay, event["address"], payload)
            else:
                _require(
                    _read(replay, event["address"], event["width"]) == payload,
                    "record copy2 model read differs",
                )
            if index in prefixes:
                snapshots[index] = _pages(replay)
        _require(
            _same_packet(result["pages"], _pages(replay)),
            "record copy2 model event pages differ",
        )
        _require(
            _same_packet(snapshots[195], prefix_pages),
            "record copy2 path installed pages differ",
        )
        sequence = [
            ("string", name, index)
            for index in range(5)
            for name in ("entry", "return")
        ]
        sequence += [
            ("path", name, index) for index, name in enumerate(child["boundaries"])
        ]
        sequence += [
            ("string", name, index)
            for index in range(5, 8)
            for name in ("entry", "return")
        ]
        _require(
            type(result["boundaries"]) is list and len(result["boundaries"]) == 23,
            "record copy2 model boundary count differs",
        )
        for row, (kind, name, index), prefix in zip(
            result["boundaries"], sequence, prefixes
        ):
            _require(
                type(row) is dict
                and set(row) == BOUNDARY_KEYS
                and all(type(k) is str for k in row),
                "record copy2 model boundary schema differs",
            )
            if kind == "path":
                expected = copy.deepcopy(child["boundaries"][name])
                expected.update(
                    kind=kind,
                    name=name,
                    index=index,
                    events=copy.deepcopy(result["events"][:195]) + expected["events"],
                )
                _require(
                    _same_packet(row, expected),
                    "record copy2 model path boundary differs",
                )
            else:
                q, t = d + STRING_OFFSETS[index], s + STRING_OFFSETS[index]
                regs = dict(
                    fixture["registers"],
                    esi=d,
                    edi=s,
                    ebp=g - 4,
                    eax=(t if index == 7 else q) if name == "entry" else q,
                    ecx=q if name == "entry" else 0,
                    edx=s + 0xF8 if index == 7 else t,
                    esp=g - 48 if name == "entry" else g - 32,
                )
                expected = dict(
                    kind=kind,
                    name=name,
                    index=index,
                    registers=regs,
                    xmm=dict(fixture["xmm"]),
                    pages=snapshots[prefix],
                    events=copy.deepcopy(result["events"][:prefix]),
                    flags=0x85,
                    flag_mask=0x8D5,
                    df=0,
                    endpoint=0x4080D0 if name == "entry" else STRING_RETURNS[index],
                )
                _require(
                    _same_packet(row, expected),
                    "record copy2 model string boundary differs",
                )
            _require(
                len(row["events"]) == prefix,
                "record copy2 model boundary prefix differs",
            )
        return copy.deepcopy(result)

    return _normalize(run)


# Literal selected instruction occurrences from pinned decoded operand facts.
PATH_TRACE = (
    633056,
    633057,
    633059,
    633060,
    633062,
    633063,
    633066,
    633072,
    633079,
    633086,
    633089,
    633091,
    633094,
    633095,
    633920,
    633921,
    633923,
    633924,
    633926,
    633927,
    633930,
    633936,
    633943,
    633950,
    633952,
    633962,
    633968,
    633970,
    633971,
    567584,
    567585,
    567587,
    567590,
    567592,
    567602,
    567607,
    567609,
    567612,
    567617,
    567650,
    567651,
    3503323,
    3503324,
    3503326,
    3503359,
    3503362,
    3645266,
    3645268,
    3645269,
    3645271,
    3645272,
    3707947,
    3707949,
    3707950,
    3707952,
    3707953,
    3707956,
    3707959,
    3707961,
    3707963,
    3707988,
    3707989,
    3707991,
    3707997,
    3708003,
    3708005,
    3708007,
    3708022,
    3708023,
    3708024,
    3503367,
    3503368,
    3503370,
    3503372,
    3503373,
    567656,
    567659,
    567661,
    567662,
    633976,
    633978,
    633981,
    633983,
    633986,
    633989,
    633991,
    633992,
    633993,
    633994,
    633100,
    633102,
    633104,
    633107,
    633108,
    633111,
    633112,
    633114,
    633116,
    568224,
    568225,
    568227,
    568230,
    568231,
    568233,
    568235,
    568237,
    568240,
    568242,
    568244,
    568246,
    568248,
    568251,
    568254,
    568257,
    568260,
    568262,
    568240,
    568242,
    568244,
    568246,
    568248,
    568251,
    568254,
    568257,
    568260,
    568262,
    568264,
    568265,
    568266,
    633121,
    633124,
    633127,
    633128,
    633130,
    633131,
    633132,
)
TRACE = (
    1423792,
    1423793,
    1423795,
    1423797,
    1423802,
    1423808,
    1423809,
    1423810,
    1423811,
    1423812,
    1423817,
    1423819,
    1423820,
    1423823,
    1423829,
    1423831,
    1423834,
    1423837,
    1423840,
    1423842,
    1423845,
    1423847,
    1423850,
    1423853,
    1423856,
    1423859,
    1423862,
    1423865,
    1423868,
    1423871,
    1423875,
    1423878,
    1423881,
    1423884,
    1423887,
    1423890,
    1423893,
    1423896,
    1423899,
    1423902,
    1423905,
    1423908,
    1423911,
    1423914,
    1423918,
    1423921,
    1423925,
    1423928,
    1423931,
    1423934,
    1423941,
    1423948,
    1423952,
    1423958,
    1423960,
    1423962,
    1423964,
    1423965,
    1423968,
    32976,
    32977,
    32979,
    32980,
    32983,
    32984,
    32986,
    32989,
    32990,
    32993,
    32995,
    33001,
    33004,
    33006,
    33008,
    33011,
    33013,
    33086,
    33089,
    33095,
    33098,
    33136,
    33138,
    33140,
    33144,
    33147,
    33163,
    33165,
    33166,
    33167,
    33168,
    33171,
    33172,
    1423973,
    1423976,
    1423983,
    1423990,
    1423993,
    1424000,
    1424004,
    1424010,
    1424012,
    1424014,
    1424016,
    1424017,
    1424020,
    32976,
    32977,
    32979,
    32980,
    32983,
    32984,
    32986,
    32989,
    32990,
    32993,
    32995,
    33001,
    33004,
    33006,
    33008,
    33011,
    33013,
    33086,
    33089,
    33095,
    33098,
    33136,
    33138,
    33140,
    33144,
    33147,
    33163,
    33165,
    33166,
    33167,
    33168,
    33171,
    33172,
    1424025,
    1424028,
    1424032,
    1424039,
    1424042,
    1424049,
    1424053,
    1424059,
    1424061,
    1424063,
    1424065,
    1424066,
    1424069,
    32976,
    32977,
    32979,
    32980,
    32983,
    32984,
    32986,
    32989,
    32990,
    32993,
    32995,
    33001,
    33004,
    33006,
    33008,
    33011,
    33013,
    33086,
    33089,
    33095,
    33098,
    33136,
    33138,
    33140,
    33144,
    33147,
    33163,
    33165,
    33166,
    33167,
    33168,
    33171,
    33172,
    1424074,
    1424080,
    1424084,
    1424091,
    1424097,
    1424104,
    1424108,
    1424114,
    1424116,
    1424118,
    1424120,
    1424121,
    1424124,
    32976,
    32977,
    32979,
    32980,
    32983,
    32984,
    32986,
    32989,
    32990,
    32993,
    32995,
    33001,
    33004,
    33006,
    33008,
    33011,
    33013,
    33086,
    33089,
    33095,
    33098,
    33136,
    33138,
    33140,
    33144,
    33147,
    33163,
    33165,
    33166,
    33167,
    33168,
    33171,
    33172,
    1424129,
    1424133,
    1424139,
    1424145,
    1424151,
    1424157,
    1424163,
    1424169,
    1424175,
    1424181,
    1424188,
    1424195,
    1424199,
    1424205,
    1424207,
    1424209,
    1424211,
    1424212,
    1424215,
    32976,
    32977,
    32979,
    32980,
    32983,
    32984,
    32986,
    32989,
    32990,
    32993,
    32995,
    33001,
    33004,
    33006,
    33008,
    33011,
    33013,
    33086,
    33089,
    33095,
    33098,
    33136,
    33138,
    33140,
    33144,
    33147,
    33163,
    33165,
    33166,
    33167,
    33168,
    33171,
    33172,
    1424220,
    1424224,
    1424230,
    1424236,
    1424242,
    1424248,
    1424254,
    1424261,
    1424267,
    1424274,
    1424280,
    1424287,
    1424293,
    1424300,
    1424306,
    1424312,
    1424318,
    1424324,
    1424325,
    633056,
    633057,
    633059,
    633060,
    633062,
    633063,
    633066,
    633072,
    633079,
    633086,
    633089,
    633091,
    633094,
    633095,
    633920,
    633921,
    633923,
    633924,
    633926,
    633927,
    633930,
    633936,
    633943,
    633950,
    633952,
    633962,
    633968,
    633970,
    633971,
    567584,
    567585,
    567587,
    567590,
    567592,
    567602,
    567607,
    567609,
    567612,
    567617,
    567650,
    567651,
    3503323,
    3503324,
    3503326,
    3503359,
    3503362,
    3645266,
    3645268,
    3645269,
    3645271,
    3645272,
    3707947,
    3707949,
    3707950,
    3707952,
    3707953,
    3707956,
    3707959,
    3707961,
    3707963,
    3707988,
    3707989,
    3707991,
    3707997,
    3708003,
    3708005,
    3708007,
    3708022,
    3708023,
    3708024,
    3503367,
    3503368,
    3503370,
    3503372,
    3503373,
    567656,
    567659,
    567661,
    567662,
    633976,
    633978,
    633981,
    633983,
    633986,
    633989,
    633991,
    633992,
    633993,
    633994,
    633100,
    633102,
    633104,
    633107,
    633108,
    633111,
    633112,
    633114,
    633116,
    568224,
    568225,
    568227,
    568230,
    568231,
    568233,
    568235,
    568237,
    568240,
    568242,
    568244,
    568246,
    568248,
    568251,
    568254,
    568257,
    568260,
    568262,
    568240,
    568242,
    568244,
    568246,
    568248,
    568251,
    568254,
    568257,
    568260,
    568262,
    568264,
    568265,
    568266,
    633121,
    633124,
    633127,
    633128,
    633130,
    633131,
    633132,
    1424330,
    1424334,
    1424340,
    1424346,
    1424352,
    1424358,
    1424364,
    1424370,
    1424377,
    1424384,
    1424388,
    1424394,
    1424396,
    1424398,
    1424400,
    1424401,
    1424404,
    32976,
    32977,
    32979,
    32980,
    32983,
    32984,
    32986,
    32989,
    32990,
    32993,
    32995,
    33001,
    33004,
    33006,
    33008,
    33011,
    33013,
    33086,
    33089,
    33095,
    33098,
    33136,
    33138,
    33140,
    33144,
    33147,
    33163,
    33165,
    33166,
    33167,
    33168,
    33171,
    33172,
    1424409,
    1424415,
    1424419,
    1424426,
    1424432,
    1424439,
    1424443,
    1424449,
    1424451,
    1424453,
    1424455,
    1424456,
    1424459,
    32976,
    32977,
    32979,
    32980,
    32983,
    32984,
    32986,
    32989,
    32990,
    32993,
    32995,
    33001,
    33004,
    33006,
    33008,
    33011,
    33013,
    33086,
    33089,
    33095,
    33098,
    33136,
    33138,
    33140,
    33144,
    33147,
    33163,
    33165,
    33166,
    33167,
    33168,
    33171,
    33172,
    1424464,
    1424468,
    1424474,
    1424480,
    1424486,
    1424492,
    1424498,
    1424504,
    1424506,
    1424508,
    1424515,
    1424522,
    1424523,
    1424526,
    32976,
    32977,
    32979,
    32980,
    32983,
    32984,
    32986,
    32989,
    32990,
    32993,
    32995,
    33001,
    33004,
    33006,
    33008,
    33011,
    33013,
    33086,
    33089,
    33095,
    33098,
    33136,
    33138,
    33140,
    33144,
    33147,
    33163,
    33165,
    33166,
    33167,
    33168,
    33171,
    33172,
    1424531,
    1424537,
    1424543,
    1424545,
    1424548,
    1424555,
    1424556,
    1424557,
    1424558,
    1424560,
    1424561,
)


def _add_flags(left, right):
    result = (left + right) & 0xFFFFFFFF
    return (
        int(left + right > 0xFFFFFFFF)
        | (int((result & 255).bit_count() % 2 == 0) << 2)
        | (int(bool((left ^ right ^ result) & 16)) << 4)
        | (int(result == 0) << 6)
        | ((result >> 31) << 7)
        | (int(bool(~(left ^ right) & (left ^ result) & 0x80000000)) << 11)
    )


def _event_law(original):
    memory = {page: bytearray(data) for page, data in original.items()}
    events = []

    def event(access, address, value):
        if access == "write":
            _write(memory, address, value.to_bytes(4, "little"))
        else:
            _require(
                int.from_bytes(_read(memory, address), "little") == value,
                "record copy2 expected read differs",
            )
        events.append(dict(access=access, address=address, width=4, value=value))

    return memory, events, event


def _boundary(regs, xmm, pages, events, endpoint, flags, mask):
    return dict(
        registers=dict(regs),
        xmm=dict(xmm),
        pages=_pages(pages),
        events=copy.deepcopy(events),
        endpoint=endpoint,
        flags=flags,
        flag_mask=mask,
        df=0,
    )


def _allocation_packet_law(registers, pages, destination, continuation, stack_base):
    """Count2 ordinary allocation, with only the installed RET sentinel rebound."""
    a = registers["esp"]
    memory, events, event = _event_law(pages)
    w = lambda at, value: event("write", at, value)
    r = lambda at, value: event("read", at, value)
    w(a - 4, registers["ebp"])
    r(a + 4, 2)
    for at, value in ((a - 8, 16), (a - 12, BASE + 0x8A968), (a - 16, a - 4)):
        w(at, value)
    r(a - 8, 16)
    for at, value in ((a - 20, 16), (a - 24, BASE + 0x357507), (a - 28, a - 16)):
        w(at, value)
    r(a - 28, a - 16)
    w(a - 28, a - 16)
    w(a - 32, registers["esi"])
    r(a - 20, 16)
    w(a - 36, 16)
    w(a - 40, 0)
    r(HEAP_GLOBAL, HEAP)
    w(a - 44, HEAP)
    r(ALLOC_IAT, IMPORT)
    w(a - 48, BASE + 0x389463)
    imported = _boundary(
        dict(registers, eax=16, esi=16, ebp=a - 28, esp=a - 48),
        {},
        memory,
        events,
        IMPORT,
        0,
        0x8C5,
    )
    for at, value in (
        (a - 32, registers["esi"]),
        (a - 28, a - 16),
        (a - 24, BASE + 0x357507),
        (a - 20, 16),
        (a - 16, a - 4),
        (a - 12, BASE + 0x8A968),
        (a - 4, registers["ebp"]),
        (a, allocator.RETURN),
    ):
        if at == a:
            # The generic law has a fixed RETURN sentinel; actual installed bytes
            # are checked below and no other event/page/pointer cell is changed.
            events.append(dict(access="read", address=a, width=4, value=value))
        else:
            r(at, value)
    wanted = dict(
        relation=dict(result=destination, request=16, metadata=None),
        registers=dict(
            registers, eax=destination, ecx=destination, edx=0xB0000001, esp=a + 8
        ),
        flags=_add_flags(a - 8, 4),
        flag_mask=0x8D5,
        stack=_read(memory, stack_base, 8192),
        payload=_read(pages, DATA, 16384),
        events=events,
    )
    child = _normalize(
        lambda: allocator._expected(
            dict(count=2, pointer=destination),
            dict(registers),
            _read(pages, stack_base, 8192),
            _read(pages, DATA, 16384),
            stack_base=stack_base,
            data_base=DATA,
        )
    )
    _require(
        _same_packet(child, wanted), "record copy2 path allocation primitive differs"
    )
    _require(
        int.from_bytes(_read(pages, a), "little") == continuation,
        "record copy2 path allocation installed continuation differs",
    )
    wanted["events"][-1]["value"] = continuation
    return wanted, imported


def _scalar_packet_law(registers, xmm, pages, source, destination, continuation):
    """Independent handwritten prediction of the complete ten-field scalar child."""
    c = registers["esp"]
    snapshot = _read(pages, source, 16)
    memory, events, event = _event_law(pages)
    event("write", c - 4, registers["ebp"])
    event("read", c + 4, destination)
    event("write", c - 8, registers["esi"])
    for offset in (0, 4, 8, 12):
        word = int.from_bytes(snapshot[offset : offset + 4], "little")
        event("read", source + offset, word)
        event("write", destination + offset, word)
    for at, value in (
        (c - 8, registers["esi"]),
        (c - 4, registers["ebp"]),
        (c, continuation),
    ):
        event("read", at, value)
    wanted = dict(
        pages=_pages(memory),
        registers=dict(
            registers,
            eax=destination + 16,
            ecx=int.from_bytes(snapshot[12:], "little"),
            esp=c + 4,
        ),
        xmm=dict(xmm),
        flags=0x44,
        flag_mask=0x8D5,
        df=0,
        endpoint=continuation,
        source_snapshot=snapshot,
        events=events,
        trace_rvas=[
            f"0x{pc:08x}"
            for pc in (
                0x8ABA0,
                0x8ABA1,
                0x8ABA3,
                0x8ABA6,
                0x8ABA7,
                0x8ABA9,
                0x8ABAB,
                0x8ABAD,
            )
            + (
                0x8ABB0,
                0x8ABB2,
                0x8ABB4,
                0x8ABB6,
                0x8ABB8,
                0x8ABBB,
                0x8ABBE,
                0x8ABC1,
                0x8ABC4,
                0x8ABC6,
            )
            * 2
            + (0x8ABC8, 0x8ABC9, 0x8ABCA)
        ],
    )
    child = _normalize(
        lambda: scalar.apply(
            pages=dict(pages),
            registers=dict(registers),
            xmm=dict(xmm),
            source=source,
            destination=destination,
            return_address=continuation,
            entry_flags=0x202,
        )
    )
    _require(_same_packet(child, wanted), "record copy2 path scalar primitive differs")
    return wanted


def _path_packet_law(
    *, pages, registers, xmm, return_address, entry_flags, allocation_result
):
    """Predict selected count-two owner and supplied successful heap response.

    Pages/state are installed inputs; no fixture, native run or API is invoked.
    The source-header third word and unused scalar arguments are preserved.
    """
    p = registers["esp"]
    j = int.from_bytes(_read(pages, p + 4), "little")
    h = registers["ecx"]
    o = int.from_bytes(_read(pages, j), "little")
    g = dict(
        entry=p,
        source=o,
        destination=allocation_result,
        source_header=j,
        destination_header=h,
    )
    stack_base = STACK
    initial = registers
    p, h, j, o, d = (
        g[k]
        for k in (
            "entry",
            "destination_header",
            "source_header",
            "source",
            "destination",
        )
    )
    memory, events, event = _event_law(pages)
    boundaries = {
        "parent_entry": _boundary(
            initial, xmm, memory, events, BASE + 0x9A8E0, entry_flags, 0xFFFFFFFF
        )
    }
    for at, value in (
        (p - 4, initial["ebp"]),
        (p - 8, initial["esi"]),
        (p - 12, initial["edi"]),
    ):
        event("write", at, value)
    event("read", p + 4, j)
    for at in (h, h + 4, h + 8):
        event("write", at, 0)
    event("read", j + 4, o + 16)
    event("read", j, o)
    event("write", p - 16, 2)
    event("write", p - 20, BASE + 0x9A90C)
    regs = dict(initial, eax=2, esi=h, edi=j, ebp=p - 4, esp=p - 20)
    boundaries["reserve_entry"] = _boundary(
        regs, xmm, memory, events, BASE + 0x9AC40, 0, 0xC5
    )
    for at, value in ((p - 24, p - 4), (p - 28, h), (p - 32, j)):
        event("write", at, value)
    event("read", p - 16, 2)
    for at in (h, h + 4, h + 8):
        event("write", at, 0)
    event("write", p - 36, 2)
    event("write", p - 40, BASE + 0x9AC78)
    regs.update(edi=2, ebp=p - 24, esp=p - 40)
    boundaries["allocation_entry"] = _boundary(
        regs, xmm, memory, events, BASE + 0x8A920, 0x95, 0x8D5
    )
    allocated, imported = _allocation_packet_law(
        regs, _pages(memory), d, BASE + 0x9AC78, stack_base
    )
    prefix = copy.deepcopy(events)
    imported["events"] = prefix + imported["events"]
    imported["xmm"] = dict(xmm)
    imported.update(entry_esp=p - 88, words=[BASE + 0x389463, HEAP, 0, 16])
    events.extend(copy.deepcopy(allocated["events"]))
    _write(memory, stack_base, allocated["stack"])
    regs = dict(allocated["registers"])
    boundaries["allocation_return"] = _boundary(
        regs, xmm, memory, events, BASE + 0x9AC78, allocated["flags"], 0x8D5
    )
    for at, value in ((h, d), (h + 4, d)):
        event("write", at, value)
    event("read", h, d)
    event("write", h + 8, d + 16)
    for at, value in (
        (p - 32, j),
        (p - 28, h),
        (p - 24, p - 4),
        (p - 20, BASE + 0x9A90C),
    ):
        event("read", at, value)
    regs.update(eax=((d + 16) & 0xFFFFFF00) | 1, edi=j, ebp=p - 4, esp=p - 12)
    boundaries["reserve_return"] = _boundary(
        regs, xmm, memory, events, BASE + 0x9A90C, allocated["flags"], 0x8D5
    )
    event("read", j + 4, o + 16)
    event("write", p - 16, d)
    event("read", p + 4, j)
    event("write", p - 20, j)
    event("write", p - 24, d)
    event("read", h, d)
    event("write", p - 28, d)
    event("read", j, o)
    event("write", p - 32, BASE + 0x9A921)
    regs.update(edx=o + 16, ecx=o, esp=p - 32)
    boundaries["scalar_entry"] = _boundary(
        regs, xmm, memory, events, BASE + 0x8ABA0, 0, 0x8C5
    )
    copied = _scalar_packet_law(regs, xmm, _pages(memory), o, d, BASE + 0x9A921)
    events.extend(copy.deepcopy(copied["events"]))
    # The original event closure refers to memory: preserve that dictionary while
    # adopting all actual child pages, rather than reseeding any native fixture.
    for page, payload in copied["pages"].items():
        memory[page][:] = payload
    regs = dict(copied["registers"])
    boundaries["scalar_return"] = _boundary(
        regs, xmm, memory, events, BASE + 0x9A921, 0x44, 0x8D5
    )
    event("write", h + 4, d + 16)
    for at, value in (
        (p - 12, initial["edi"]),
        (p - 8, initial["esi"]),
        (p - 4, initial["ebp"]),
        (p, return_address),
    ):
        event("read", at, value)
    regs.update(
        eax=h, esi=initial["esi"], edi=initial["edi"], ebp=initial["ebp"], esp=p + 8
    )
    _require(
        len(PATH_TRACE) == 136 and len(events) == 83,
        "record copy2 path source count differs",
    )
    return dict(
        geometry=g,
        registers=regs,
        xmm=dict(xmm),
        flags=_add_flags(p - 28, 16),
        flag_mask=0x8D5,
        df=0,
        endpoint=return_address,
        pages=_pages(memory),
        events=events,
        trace_rvas=[f"0x{pc:08x}" for pc in PATH_TRACE],
        boundaries=boundaries,
        allocation_packet=allocated,
        scalar_packet=copied,
        imported=imported,
        source_snapshot=_read(pages, o, 16),
    )


def _preflight(sources):
    def run():
        _require(
            type(sources) is dict and set(sources) == set(SOURCE_PINS),
            "record copy2 source partition differs",
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
            "record copy2 source build differs",
        )
        atlas = {
            int(row["entry_rva"], 16): row
            for row in sources["program_facts"]["functions"]
        }
        _require(
            len(atlas) == len(sources["program_facts"]["functions"]),
            "record copy2 duplicate atlas entry",
        )
        for start, (size, digest) in BODY_PINS.items():
            row = atlas[start]
            _require(
                type(row["body_size"]) is int
                and row["body_size"] == size
                and row["body_sha256"] == digest
                and row["ranges"] == [dict(start_rva=f"0x{start:08x}", size=size)],
                "record copy2 atlas body differs",
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
            "record copy2 direct code identity differs",
        )
        _require(
            points == sorted(points, key=lambda p: int(p["rva"], 16)),
            "record copy2 direct point order differs",
        )
        allowed = {}
        for start, size in BODIES:
            _require(
                type(codes[start]) is bytes
                and len(codes[start]) == size
                and hashlib.sha256(codes[start]).hexdigest() == BODY_PINS[start][1],
                "record copy2 direct body differs",
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
                    "record copy2 direct point differs",
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
                    "record copy2 direct bytes differ",
                )
                allowed[pc] = point
                cursor += point["size"]
            _require(cursor == start + size, "record copy2 direct extent differs")
        _require(
            len(allowed) == len(points) == 498,
            "record copy2 direct partition differs",
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
            "record copy2 executable differs",
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


PATH_NAMES = (
    "parent_entry",
    "reserve_entry",
    "allocation_entry",
    "allocation_return",
    "reserve_return",
    "scalar_entry",
    "scalar_return",
)
CONTROL_ROLES = ("outer_entry", "string_entry", "string_return") + tuple(
    "path_" + name for name in PATH_NAMES
)
CONTROLS = {
    **{
        role + "_" + kind: "record copy2 " + role.replace("_", " ") + " differs"
        for role in CONTROL_ROLES
        for kind in ("gpr", "xmm", "flags", "df", "page")
    },
    **{
        name: "record copy2 ordered memory differs"
        for name in ("caller_source", "source_size", "destination_capacity")
    },
    **{
        name: "record copy2 final pages differ"
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
            "path_source",
            "path_buffer",
            "path_capacity",
            "heap_padding",
            "iat_padding",
        )
    },
    **{
        name: "record copy2 final ABI differs"
        for name in (
            "final_gpr",
            "final_edx",
            "final_xmm",
            "final_flags",
            "final_df",
            "final_endpoint",
        )
    },
    "missing_read_record": "record copy2 final events differ",
    "restored_write_record": "record copy2 final events differ",
    "trace_record": "record copy2 final native path differs",
    "heap_request": "record copy2 allocation handoff differs",
    **{
        name: "record copy2 allocation imported ABI differs"
        for name in ("heap_gpr", "heap_xmm", "heap_flags", "heap_df", "heap_page")
    },
    **{
        name: "record copy2 supplied response preservation differs"
        for name in (
            "response_result",
            "response_gpr",
            "response_xmm",
            "response_page",
            "response_flags",
        )
    },
    "reserve_full_eax": "record copy2 path reserve return differs",
}


def _run_case(codes, points, vector, negative=None, *, capture=None):
    _require(
        negative is None or type(negative) is str and negative in CONTROLS,
        "invalid record copy2 control",
    )
    fixture = _fixture(vector)
    wanted = _expected(vector, fixture)
    allowed = _checked_code_packet(codes, points)
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "record copy2 reviewed Unicorn required")
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    machine.ctl_set_cpu_model(CPU_MODEL)
    _require(machine.ctl_get_cpu_model() == CPU_MODEL, "record copy2 CPU differs")
    g, d = fixture["registers"]["esp"], fixture["registers"]["ecx"]
    s = wanted["source_address"]
    stop = fixture["return_address"]
    code_pages = {
        (BASE + pc) & ~4095
        for start, size in BODIES
        for pc in range(start, start + size)
    } | {stop & ~4095, IMPORT}
    _require(
        not code_pages.intersection(fixture["pages"]),
        "record copy2 mappings overlap",
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
    summaries = []
    cursor = 0
    resume = None
    imported = copy.deepcopy(wanted["path_packet"]["imported"])
    imported["events"] = copy.deepcopy(wanted["events"][:195]) + imported["events"]
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
            if negative == "reserve_full_eax" and role == "path_reserve_return":
                machine.reg_write(ids["eax"], 1)
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
            "record copy2 " + role.replace("_", " ") + " differs",
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
        nonlocal cursor, resume
        if address == stop:
            m.emu_stop()
            return
        if address == IMPORT:
            _require(not summaries, "record copy2 repeated allocation response")
            sp = m.reg_read(ids["esp"])
            words = [
                int.from_bytes(m.mem_read(sp + 4 * i, 4), "little") for i in range(4)
            ]
            if negative == "heap_request":
                words[3] ^= 1
                flip(sp + 12)
            _require(
                sp == imported["entry_esp"] and words == imported["words"],
                "record copy2 allocation handoff differs",
            )
            if negative == "heap_gpr":
                m.reg_write(ids["edx"], m.reg_read(ids["edx"]) ^ 1)
            if negative == "heap_xmm":
                m.reg_write(xmm_ids["xmm7"], m.reg_read(xmm_ids["xmm7"]) ^ 1)
            if negative in ("heap_flags", "heap_df"):
                m.reg_write(
                    x.UC_X86_REG_EFLAGS,
                    m.reg_read(x.UC_X86_REG_EFLAGS)
                    ^ (0x400 if negative == "heap_df" else 1),
                )
            if negative == "heap_page":
                flip(d + 0x15)
            raw = m.reg_read(x.UC_X86_REG_EFLAGS)
            actual = dict(
                registers={name: m.reg_read(reg) for name, reg in ids.items()},
                xmm={name: m.reg_read(reg) for name, reg in xmm_ids.items()},
                pages={
                    page: bytes(m.mem_read(page, 4096)) for page in fixture["pages"]
                },
                events=copy.deepcopy(events),
                flags=raw & imported["flag_mask"],
                flag_mask=imported["flag_mask"],
                df=(raw >> 10) & 1,
                endpoint=m.reg_read(x.UC_X86_REG_EIP),
            )
            _require(
                _same_packet(actual, {key: imported[key] for key in actual}),
                "record copy2 allocation imported ABI differs",
            )
            summaries.append(
                dict(
                    role="allocation",
                    registers=actual["registers"],
                    xmm=actual["xmm"],
                    eflags=raw,
                    flags=actual["flags"],
                    flag_mask=actual["flag_mask"],
                    df=actual["df"],
                    endpoint=actual["endpoint"],
                    pages_sha256=_page_hashes(actual["pages"]),
                    events_sha256=_canonical_sha256(events),
                    entry_esp=sp,
                    words=list(words),
                )
            )
            response = dict(
                imported["registers"],
                eax=fixture["allocation_result"],
                ecx=0xA0000001,
                edx=0xB0000001,
                esp=sp + 16,
            )
            for name in ("eax", "ecx", "edx", "esp"):
                m.reg_write(ids[name], response[name])
            m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            if negative == "response_result":
                m.reg_write(ids["eax"], 0)
            if negative == "response_gpr":
                m.reg_write(ids["ebx"], m.reg_read(ids["ebx"]) ^ 1)
            if negative == "response_xmm":
                m.reg_write(xmm_ids["xmm6"], m.reg_read(xmm_ids["xmm6"]) ^ 1)
            if negative == "response_page":
                flip(d + 0x15)
            if negative == "response_flags":
                m.reg_write(x.UC_X86_REG_EFLAGS, 0x247)
            _require(
                _same_packet(
                    {name: m.reg_read(reg) for name, reg in ids.items()}, response
                )
                and _same_packet(
                    {name: m.reg_read(reg) for name, reg in xmm_ids.items()},
                    imported["xmm"],
                )
                and m.reg_read(x.UC_X86_REG_EFLAGS) == 0x246
                and all(
                    bytes(m.mem_read(page, 4096)) == payload
                    for page, payload in imported["pages"].items()
                ),
                "record copy2 supplied response preservation differs",
            )
            resume = words[0]
            m.emu_stop()
            return
        pc = address - BASE
        _require(
            pc in allowed and size == allowed[pc]["size"],
            "record copy2 escaped selected code",
        )
        if pc == 0x15B9B0:
            _require(not trace and not boundaries, "record copy2 repeated outer entry")
            check_boundary(outer, "outer_entry")
        if cursor < 23:
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
            "record copy2 native path differs",
        )

    def on_memory(m, access, address, width, value, user):
        _require(width in (1, 4), "record copy2 access width differs")
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
            len(events) < 372 and _same_packet(row, wanted["events"][len(events)]),
            "record copy2 ordered memory differs",
        )
        events.append(row)

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    machine.emu_start(BASE + 0x15B9B0, 0, count=10000)
    _require(
        resume is not None and len(summaries) == 1,
        "record copy2 allocation response missing",
    )
    machine.emu_start(resume, 0, count=10000)
    corrupt = dict(
        field=d + 0x34,
        padding=d + 0x15,
        source=s,
        source_padding=s + 0x15,
        source_capacity=s + 0x38 + 20,
        source_terminator=s + 0x38,
        stack_ancestor=g + 8,
        stack_padding=g - 132,
        seh=0,
        cookie=COOKIE,
        random_padding=DEST_PAGE + 1,
        path_source=int.from_bytes(_read(fixture["pages"], s + 0xCC), "little"),
        path_buffer=fixture["allocation_result"],
        path_capacity=s + 0xD4,
        heap_padding=(HEAP_GLOBAL & ~4095) + 1,
        iat_padding=(ALLOC_IAT & ~4095) + 1,
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
        "record copy2 final ABI differs",
    )
    _require(_same_packet(pages, wanted["pages"]), "record copy2 final pages differ")
    _require(_same_packet(events, wanted["events"]), "record copy2 final events differ")
    _require(
        _same_packet(trace, wanted["trace_rvas"]),
        "record copy2 final native path differs",
    )
    _require(cursor == 23 and len(boundaries) == 24, "record copy2 missing boundaries")
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
        summaries=summaries,
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
                "record copy2 incidental control: " + name + ": " + str(exc),
            )
            controls.append(dict(name=name, rejected=True, reason=reason))
        else:
            raise ConformanceError("record copy2 control survived: " + name)
    executed = sorted({pc for row in observations for pc in row["trace_rvas"]})
    _require(
        set(executed) == {f"0x{pc:08x}" for pc in TRACE},
        "record copy2 native coverage differs",
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
            path_clone_calls=n,
            reserve_calls=n,
            allocation_snapshots=sum(len(row["summaries"]) for row in observations),
            source_bytes_preserved=308 * n,
            record_bytes=308 * n,
            record_written_bytes=183 * n,
            record_padding_bytes_preserved=125 * n,
            copied_scalar_bytes=99 * n,
            empty_string_field_bytes=72 * n,
            path_header_bytes=12 * n,
            copied_path_bytes=16 * n,
            path_source_bytes_preserved=16 * n,
            xmm_preserved_cases=n,
            allocation_requests=n,
            requested_allocation_bytes=16 * n,
            free_requests=0,
            scalar_clone_calls=n,
            wide_reads=0,
            wide_writes=0,
            api_responses=n,
            cookie_checker_calls=0,
            opaque_instructions=0,
            controls=len(controls),
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Finite continuous normal movement record copy with eight empty inline strings and a two-record source path",
            premises=[
                "Exactly 48 synthetic alignment and profile recipes with positive disjoint complete 308-byte source and destination records crossing page boundaries",
                "One CPU19 Unicorn executes the owner eight empty-string assignments two-record path clone reserve ordinary allocation chain and scalar clone continuously; execution pauses only for one supplied successful HeapAlloc response",
                "All eight source inline strings have size zero capacity fifteen and first byte zero; the source path contains exactly two eight-byte records; its supplied capacity word is preserved and unread",
                "Complete fifteen-field model packet and complete path child packet are checked against separate destination183 source308 path16 full pages saved stack and final ABI equations and literal591 instruction trace before execution",
                "Model event replay checks typed372 access records and page consistency; actual native online checks and independent test oracles establish the complete ordered accesses",
                "All eight general and XMM registers full pages ordered event prefixes defined flags DF and PC are checked at outer entry and twenty-three sequential kind name and index helper boundaries; one imported allocation packet is checked before its response",
                "FS base zero with source SEH and cookie slots supplied; saved SEH and cached cookie restore normally with no cookie checker or failure-handler execution",
                "Destination scalar fields copy arbitrary source bit patterns; path header and empty string fields are written while all125 destination padding bytes complete source308 and path source16 are preserved",
                "The supplied allocation response returns one disjoint mapped sixteen-byte destination and preserves full pages nonvolatile general registers and all eight XMM registers; selected native code establishes the ordinary allocation relation in this finite domain",
                "Architecturally defined flag masks and DF zero are distinct from recorded raw finite VM EFLAGS",
            ],
            not_claimed=[
                "Allocator API execution ownership unmapping destruction exception unwind failure handler cookie validation operating-system or hardware execution",
                "Nonempty strings other path lengths record assignment vector append receiver growth AddMove greater than one AddCharge gameplay or Lua reachability",
                "Model event replay count and trace alone reject every coordinated same-count event forgery before execution",
                "Missing restored-write and trace record mutations establish execution of represented writes or instructions",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "record copy2 executable changed",
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
            "sealed record copy2 receipt differs",
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
            "record copy2 native rebuild differs",
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
