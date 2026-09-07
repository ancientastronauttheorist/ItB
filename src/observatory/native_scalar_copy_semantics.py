"""Feature-zero scalar and REP copy paths with an independent snapshot oracle."""

from __future__ import annotations
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
import capstone
import capstone.x86_const as x86
from src.observatory import native_small_copy_semantics as small
from src.observatory import native_vector_resize_semantics as resize
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _canonical_bytes,
    _canonical_sha256,
    _source_identity,
    _validate_json_tree,
    _assert_publication_safe,
    _load_executable,
    _decode_body,
    _point,
)

SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_scalar_copy_semantics"
SEALED_SHA256 = "f15d777d0015508025011c796882044f5f9f79f3eeb09fd9fd714bb2ae8fd428"
SOURCE_PINS = {
    "program_facts": resize.SOURCE_PINS["program_facts"],
    "small_copy_semantics": (small.ANALYSIS_KIND, small.SEALED_SHA256),
}
START = 0x36E580
SCALAR_RANGES = (
    (3597696, 3597737),
    (3597737, 3597774),
    (3597783, 3597822),
    (3598247, 3598300),
    (3598324, 3598331),
    (3598332, 3598343),
    (3598344, 3598361),
    (3598364, 3598387),
    (3598388, 3598403),
    (3598403, 3598479),
    (3598496, 3598503),
    (3598504, 3598517),
    (3598520, 3598539),
    (3598540, 3598565),
    (3598740, 3598795),
    (3598971, 3599031),
)
FULL_RANGES = (
    (0x36E580, 604),
    (0x36E7F4, 7),
    (0x36E7FC, 11),
    (0x36E808, 17),
    (0x36E81C, 23),
    (0x36E834, 91),
    (0x36E8A0, 7),
    (0x36E8A8, 13),
    (0x36E8B8, 19),
    (0x36E8CC, 255),
    (0x36E9D0, 231),
    (0x36EAC0, 52),
)
TABLES = {
    0x36E7E4: [0x36E7F4, 0x36E7FC, 0x36E808, 0x36E81C],
    0x36E890: [0x36E8A0, 0x36E8A8, 0x36E8B8, 0x36E8CC],
}
U32, PAYLOAD = 0xFFFFFFFF, 0x10000000


def R(name):
    return ("reg", name)


def I(value):
    return ("imm", value)


def M(base, offset=0, index=None, width=4):
    return ("mem", base, offset, index, width)


OPS = {
    3597696: ("push", ("reg", "edi")),
    3597697: ("push", ("reg", "esi")),
    3597698: ("mov", ("reg", "esi"), ("mem", "esp", 16, None, 4, 1)),
    3597702: ("mov", ("reg", "ecx"), ("mem", "esp", 20, None, 4, 1)),
    3597706: ("mov", ("reg", "edi"), ("mem", "esp", 12, None, 4, 1)),
    3597710: ("mov", ("reg", "eax"), ("reg", "ecx")),
    3597712: ("mov", ("reg", "edx"), ("reg", "ecx")),
    3597714: ("add", ("reg", "eax"), ("reg", "esi")),
    3597716: ("cmp", ("reg", "edi"), ("reg", "esi")),
    3597718: ("jbe", ("imm", 7792032)),
    3597720: ("cmp", ("reg", "edi"), ("reg", "eax")),
    3597722: ("jb", ("imm", 7792692)),
    3597728: ("cmp", ("reg", "ecx"), ("imm", 32)),
    3597731: ("jb", ("imm", 7793275)),
    3597737: ("cmp", ("reg", "ecx"), ("imm", 128)),
    3597743: ("jae", ("imm", 7792068)),
    3597745: ("bt", ("mem", None, 8994608, None, 4, 1), ("imm", 1)),
    3597753: ("jb", ("imm", 7793229)),
    3597759: ("jmp", ("imm", 7792551)),
    3597764: ("bt", ("mem", None, 9137736, None, 4, 1), ("imm", 1)),
    3597772: ("jae", ("imm", 7792087)),
    3597783: ("mov", ("reg", "eax"), ("reg", "edi")),
    3597785: ("xor", ("reg", "eax"), ("reg", "esi")),
    3597787: ("test", ("reg", "eax"), ("imm", 15)),
    3597792: ("jne", ("imm", 7792112)),
    3597794: ("bt", ("mem", None, 8994608, None, 4, 1), ("imm", 1)),
    3597802: ("jb", ("imm", 7793104)),
    3597808: ("bt", ("mem", None, 9137736, None, 4, 1), ("imm", 0)),
    3597816: ("jae", ("imm", 7792551)),
    3598247: ("test", ("reg", "edi"), ("imm", 3)),
    3598253: ("je", ("imm", 7792578)),
    3598255: ("mov", ("reg", "al"), ("mem", "esi", 0, None, 1, 1)),
    3598257: ("mov", ("mem", "edi", 0, None, 1, 1), ("reg", "al")),
    3598259: ("dec", ("reg", "ecx")),
    3598260: ("add", ("reg", "esi"), ("imm", 1)),
    3598263: ("add", ("reg", "edi"), ("imm", 1)),
    3598266: ("test", ("reg", "edi"), ("imm", 3)),
    3598272: ("jne", ("imm", 7792559)),
    3598274: ("mov", ("reg", "edx"), ("reg", "ecx")),
    3598276: ("cmp", ("reg", "ecx"), ("imm", 32)),
    3598279: ("jb", ("imm", 7793275)),
    3598285: ("shr", ("reg", "ecx"), ("imm", 2)),
    3598288: (
        "rep movsd",
        ("mem", "edi", 0, None, 4, 1),
        ("mem", "esi", 0, None, 4, 1),
    ),
    3598290: ("and", ("reg", "edx"), ("imm", 3)),
    3598293: ("jmp", ("mem", None, 7792612, "edx", 4, 4)),
    3598324: ("mov", ("reg", "eax"), ("mem", "esp", 12, None, 4, 1)),
    3598328: ("pop", ("reg", "esi")),
    3598329: ("pop", ("reg", "edi")),
    3598330: ("ret",),
    3598332: ("mov", ("reg", "al"), ("mem", "esi", 0, None, 1, 1)),
    3598334: ("mov", ("mem", "edi", 0, None, 1, 1), ("reg", "al")),
    3598336: ("mov", ("reg", "eax"), ("mem", "esp", 12, None, 4, 1)),
    3598340: ("pop", ("reg", "esi")),
    3598341: ("pop", ("reg", "edi")),
    3598342: ("ret",),
    3598344: ("mov", ("reg", "al"), ("mem", "esi", 0, None, 1, 1)),
    3598346: ("mov", ("mem", "edi", 0, None, 1, 1), ("reg", "al")),
    3598348: ("mov", ("reg", "al"), ("mem", "esi", 1, None, 1, 1)),
    3598351: ("mov", ("mem", "edi", 1, None, 1, 1), ("reg", "al")),
    3598354: ("mov", ("reg", "eax"), ("mem", "esp", 12, None, 4, 1)),
    3598358: ("pop", ("reg", "esi")),
    3598359: ("pop", ("reg", "edi")),
    3598360: ("ret",),
    3598364: ("mov", ("reg", "al"), ("mem", "esi", 0, None, 1, 1)),
    3598366: ("mov", ("mem", "edi", 0, None, 1, 1), ("reg", "al")),
    3598368: ("mov", ("reg", "al"), ("mem", "esi", 1, None, 1, 1)),
    3598371: ("mov", ("mem", "edi", 1, None, 1, 1), ("reg", "al")),
    3598374: ("mov", ("reg", "al"), ("mem", "esi", 2, None, 1, 1)),
    3598377: ("mov", ("mem", "edi", 2, None, 1, 1), ("reg", "al")),
    3598380: ("mov", ("reg", "eax"), ("mem", "esp", 12, None, 4, 1)),
    3598384: ("pop", ("reg", "esi")),
    3598385: ("pop", ("reg", "edi")),
    3598386: ("ret",),
    3598388: ("lea", ("reg", "esi"), ("mem", "ecx", 0, "esi", 4, 1)),
    3598391: ("lea", ("reg", "edi"), ("mem", "ecx", 0, "edi", 4, 1)),
    3598394: ("cmp", ("reg", "ecx"), ("imm", 32)),
    3598397: ("jb", ("imm", 7793044)),
    3598403: ("bt", ("mem", None, 8994608, None, 4, 1), ("imm", 1)),
    3598411: ("jb", ("imm", 7792869)),
    3598417: ("test", ("reg", "edi"), ("imm", 3)),
    3598423: ("je", ("imm", 7792749)),
    3598425: ("mov", ("reg", "edx"), ("reg", "edi")),
    3598427: ("and", ("reg", "edx"), ("imm", 3)),
    3598430: ("sub", ("reg", "ecx"), ("reg", "edx")),
    3598432: ("mov", ("reg", "al"), ("mem", "esi", -1, None, 1, 1)),
    3598435: ("mov", ("mem", "edi", -1, None, 1, 1), ("reg", "al")),
    3598438: ("dec", ("reg", "esi")),
    3598439: ("dec", ("reg", "edi")),
    3598440: ("sub", ("reg", "edx"), ("imm", 1)),
    3598443: ("jne", ("imm", 7792736)),
    3598445: ("cmp", ("reg", "ecx"), ("imm", 32)),
    3598448: ("jb", ("imm", 7793044)),
    3598454: ("mov", ("reg", "edx"), ("reg", "ecx")),
    3598456: ("shr", ("reg", "ecx"), ("imm", 2)),
    3598459: ("and", ("reg", "edx"), ("imm", 3)),
    3598462: ("sub", ("reg", "esi"), ("imm", 4)),
    3598465: ("sub", ("reg", "edi"), ("imm", 4)),
    3598468: ("std",),
    3598469: (
        "rep movsd",
        ("mem", "edi", 0, None, 4, 1),
        ("mem", "esi", 0, None, 4, 1),
    ),
    3598471: ("cld",),
    3598472: ("jmp", ("mem", None, 7792784, "edx", 4, 4)),
    3598496: ("mov", ("reg", "eax"), ("mem", "esp", 12, None, 4, 1)),
    3598500: ("pop", ("reg", "esi")),
    3598501: ("pop", ("reg", "edi")),
    3598502: ("ret",),
    3598504: ("mov", ("reg", "al"), ("mem", "esi", 3, None, 1, 1)),
    3598507: ("mov", ("mem", "edi", 3, None, 1, 1), ("reg", "al")),
    3598510: ("mov", ("reg", "eax"), ("mem", "esp", 12, None, 4, 1)),
    3598514: ("pop", ("reg", "esi")),
    3598515: ("pop", ("reg", "edi")),
    3598516: ("ret",),
    3598520: ("mov", ("reg", "al"), ("mem", "esi", 3, None, 1, 1)),
    3598523: ("mov", ("mem", "edi", 3, None, 1, 1), ("reg", "al")),
    3598526: ("mov", ("reg", "al"), ("mem", "esi", 2, None, 1, 1)),
    3598529: ("mov", ("mem", "edi", 2, None, 1, 1), ("reg", "al")),
    3598532: ("mov", ("reg", "eax"), ("mem", "esp", 12, None, 4, 1)),
    3598536: ("pop", ("reg", "esi")),
    3598537: ("pop", ("reg", "edi")),
    3598538: ("ret",),
    3598540: ("mov", ("reg", "al"), ("mem", "esi", 3, None, 1, 1)),
    3598543: ("mov", ("mem", "edi", 3, None, 1, 1), ("reg", "al")),
    3598546: ("mov", ("reg", "al"), ("mem", "esi", 2, None, 1, 1)),
    3598549: ("mov", ("mem", "edi", 2, None, 1, 1), ("reg", "al")),
    3598552: ("mov", ("reg", "al"), ("mem", "esi", 1, None, 1, 1)),
    3598555: ("mov", ("mem", "edi", 1, None, 1, 1), ("reg", "al")),
    3598558: ("mov", ("reg", "eax"), ("mem", "esp", 12, None, 4, 1)),
    3598562: ("pop", ("reg", "esi")),
    3598563: ("pop", ("reg", "edi")),
    3598564: ("ret",),
    3598740: ("test", ("reg", "ecx"), ("imm", 4294967292)),
    3598746: ("je", ("imm", 7793073)),
    3598748: ("sub", ("reg", "edi"), ("imm", 4)),
    3598751: ("sub", ("reg", "esi"), ("imm", 4)),
    3598754: ("mov", ("reg", "eax"), ("mem", "esi", 0, None, 4, 1)),
    3598756: ("mov", ("mem", "edi", 0, None, 4, 1), ("reg", "eax")),
    3598758: ("sub", ("reg", "ecx"), ("imm", 4)),
    3598761: ("test", ("reg", "ecx"), ("imm", 4294967292)),
    3598767: ("jne", ("imm", 7793052)),
    3598769: ("test", ("reg", "ecx"), ("reg", "ecx")),
    3598771: ("je", ("imm", 7793092)),
    3598773: ("sub", ("reg", "edi"), ("imm", 1)),
    3598776: ("sub", ("reg", "esi"), ("imm", 1)),
    3598779: ("mov", ("reg", "al"), ("mem", "esi", 0, None, 1, 1)),
    3598781: ("mov", ("mem", "edi", 0, None, 1, 1), ("reg", "al")),
    3598783: ("sub", ("reg", "ecx"), ("imm", 1)),
    3598786: ("jne", ("imm", 7793077)),
    3598788: ("mov", ("reg", "eax"), ("mem", "esp", 12, None, 4, 1)),
    3598792: ("pop", ("reg", "esi")),
    3598793: ("pop", ("reg", "edi")),
    3598794: ("ret",),
    3598971: ("and", ("reg", "ecx"), ("imm", 31)),
    3598974: ("je", ("imm", 7793328)),
    3598976: ("mov", ("reg", "eax"), ("reg", "ecx")),
    3598978: ("shr", ("reg", "ecx"), ("imm", 2)),
    3598981: ("je", ("imm", 7793302)),
    3598983: ("mov", ("reg", "edx"), ("mem", "esi", 0, None, 4, 1)),
    3598985: ("mov", ("mem", "edi", 0, None, 4, 1), ("reg", "edx")),
    3598987: ("add", ("reg", "edi"), ("imm", 4)),
    3598990: ("add", ("reg", "esi"), ("imm", 4)),
    3598993: ("sub", ("reg", "ecx"), ("imm", 1)),
    3598996: ("jne", ("imm", 7793287)),
    3598998: ("mov", ("reg", "ecx"), ("reg", "eax")),
    3599000: ("and", ("reg", "ecx"), ("imm", 3)),
    3599003: ("je", ("imm", 7793328)),
    3599005: ("mov", ("reg", "al"), ("mem", "esi", 0, None, 1, 1)),
    3599007: ("mov", ("mem", "edi", 0, None, 1, 1), ("reg", "al")),
    3599009: ("inc", ("reg", "esi")),
    3599010: ("inc", ("reg", "edi")),
    3599011: ("dec", ("reg", "ecx")),
    3599012: ("jne", ("imm", 7793309)),
    3599014: ("lea", ("reg", "esp"), ("mem", "esp", 0, None, 4, 1)),
    3599021: ("lea", ("reg", "ecx"), ("mem", "ecx", 0, None, 4, 1)),
    3599024: ("mov", ("reg", "eax"), ("mem", "esp", 12, None, 4, 1)),
    3599028: ("pop", ("reg", "esi")),
    3599029: ("pop", ("reg", "edi")),
    3599030: ("ret",),
}
ORDER = sorted(OPS)
SIZES = {
    3597696: 1,
    3597697: 1,
    3597698: 4,
    3597702: 4,
    3597706: 4,
    3597710: 2,
    3597712: 2,
    3597714: 2,
    3597716: 2,
    3597718: 2,
    3597720: 2,
    3597722: 6,
    3597728: 3,
    3597731: 6,
    3597737: 6,
    3597743: 2,
    3597745: 8,
    3597753: 6,
    3597759: 5,
    3597764: 8,
    3597772: 2,
    3597783: 2,
    3597785: 2,
    3597787: 5,
    3597792: 2,
    3597794: 8,
    3597802: 6,
    3597808: 8,
    3597816: 6,
    3598247: 6,
    3598253: 2,
    3598255: 2,
    3598257: 2,
    3598259: 1,
    3598260: 3,
    3598263: 3,
    3598266: 6,
    3598272: 2,
    3598274: 2,
    3598276: 3,
    3598279: 6,
    3598285: 3,
    3598288: 2,
    3598290: 3,
    3598293: 7,
    3598324: 4,
    3598328: 1,
    3598329: 1,
    3598330: 1,
    3598332: 2,
    3598334: 2,
    3598336: 4,
    3598340: 1,
    3598341: 1,
    3598342: 1,
    3598344: 2,
    3598346: 2,
    3598348: 3,
    3598351: 3,
    3598354: 4,
    3598358: 1,
    3598359: 1,
    3598360: 1,
    3598364: 2,
    3598366: 2,
    3598368: 3,
    3598371: 3,
    3598374: 3,
    3598377: 3,
    3598380: 4,
    3598384: 1,
    3598385: 1,
    3598386: 1,
    3598388: 3,
    3598391: 3,
    3598394: 3,
    3598397: 6,
    3598403: 8,
    3598411: 6,
    3598417: 6,
    3598423: 2,
    3598425: 2,
    3598427: 3,
    3598430: 2,
    3598432: 3,
    3598435: 3,
    3598438: 1,
    3598439: 1,
    3598440: 3,
    3598443: 2,
    3598445: 3,
    3598448: 6,
    3598454: 2,
    3598456: 3,
    3598459: 3,
    3598462: 3,
    3598465: 3,
    3598468: 1,
    3598469: 2,
    3598471: 1,
    3598472: 7,
    3598496: 4,
    3598500: 1,
    3598501: 1,
    3598502: 1,
    3598504: 3,
    3598507: 3,
    3598510: 4,
    3598514: 1,
    3598515: 1,
    3598516: 1,
    3598520: 3,
    3598523: 3,
    3598526: 3,
    3598529: 3,
    3598532: 4,
    3598536: 1,
    3598537: 1,
    3598538: 1,
    3598540: 3,
    3598543: 3,
    3598546: 3,
    3598549: 3,
    3598552: 3,
    3598555: 3,
    3598558: 4,
    3598562: 1,
    3598563: 1,
    3598564: 1,
    3598740: 6,
    3598746: 2,
    3598748: 3,
    3598751: 3,
    3598754: 2,
    3598756: 2,
    3598758: 3,
    3598761: 6,
    3598767: 2,
    3598769: 2,
    3598771: 2,
    3598773: 3,
    3598776: 3,
    3598779: 2,
    3598781: 2,
    3598783: 3,
    3598786: 2,
    3598788: 4,
    3598792: 1,
    3598793: 1,
    3598794: 1,
    3598971: 3,
    3598974: 2,
    3598976: 2,
    3598978: 3,
    3598981: 2,
    3598983: 2,
    3598985: 2,
    3598987: 3,
    3598990: 3,
    3598993: 3,
    3598996: 2,
    3598998: 2,
    3599000: 3,
    3599003: 2,
    3599005: 2,
    3599007: 2,
    3599009: 1,
    3599010: 1,
    3599011: 1,
    3599012: 2,
    3599014: 7,
    3599021: 3,
    3599024: 4,
    3599028: 1,
    3599029: 1,
    3599030: 1,
}
WIDTHS = {
    3597696: [4],
    3597697: [4],
    3597698: [4, 4],
    3597702: [4, 4],
    3597706: [4, 4],
    3597710: [4, 4],
    3597712: [4, 4],
    3597714: [4, 4],
    3597716: [4, 4],
    3597718: [4],
    3597720: [4, 4],
    3597722: [4],
    3597728: [4, 4],
    3597731: [4],
    3597737: [4, 4],
    3597743: [4],
    3597745: [4, 1],
    3597753: [4],
    3597759: [4],
    3597764: [4, 1],
    3597772: [4],
    3597783: [4, 4],
    3597785: [4, 4],
    3597787: [4, 4],
    3597792: [4],
    3597794: [4, 1],
    3597802: [4],
    3597808: [4, 1],
    3597816: [4],
    3598247: [4, 4],
    3598253: [4],
    3598255: [1, 1],
    3598257: [1, 1],
    3598259: [4],
    3598260: [4, 4],
    3598263: [4, 4],
    3598266: [4, 4],
    3598272: [4],
    3598274: [4, 4],
    3598276: [4, 4],
    3598279: [4],
    3598285: [4, 1],
    3598288: [4, 4],
    3598290: [4, 4],
    3598293: [4],
    3598324: [4, 4],
    3598328: [4],
    3598329: [4],
    3598330: [],
    3598332: [1, 1],
    3598334: [1, 1],
    3598336: [4, 4],
    3598340: [4],
    3598341: [4],
    3598342: [],
    3598344: [1, 1],
    3598346: [1, 1],
    3598348: [1, 1],
    3598351: [1, 1],
    3598354: [4, 4],
    3598358: [4],
    3598359: [4],
    3598360: [],
    3598364: [1, 1],
    3598366: [1, 1],
    3598368: [1, 1],
    3598371: [1, 1],
    3598374: [1, 1],
    3598377: [1, 1],
    3598380: [4, 4],
    3598384: [4],
    3598385: [4],
    3598386: [],
    3598388: [4, 4],
    3598391: [4, 4],
    3598394: [4, 4],
    3598397: [4],
    3598403: [4, 1],
    3598411: [4],
    3598417: [4, 4],
    3598423: [4],
    3598425: [4, 4],
    3598427: [4, 4],
    3598430: [4, 4],
    3598432: [1, 1],
    3598435: [1, 1],
    3598438: [4],
    3598439: [4],
    3598440: [4, 4],
    3598443: [4],
    3598445: [4, 4],
    3598448: [4],
    3598454: [4, 4],
    3598456: [4, 1],
    3598459: [4, 4],
    3598462: [4, 4],
    3598465: [4, 4],
    3598468: [],
    3598469: [4, 4],
    3598471: [],
    3598472: [4],
    3598496: [4, 4],
    3598500: [4],
    3598501: [4],
    3598502: [],
    3598504: [1, 1],
    3598507: [1, 1],
    3598510: [4, 4],
    3598514: [4],
    3598515: [4],
    3598516: [],
    3598520: [1, 1],
    3598523: [1, 1],
    3598526: [1, 1],
    3598529: [1, 1],
    3598532: [4, 4],
    3598536: [4],
    3598537: [4],
    3598538: [],
    3598540: [1, 1],
    3598543: [1, 1],
    3598546: [1, 1],
    3598549: [1, 1],
    3598552: [1, 1],
    3598555: [1, 1],
    3598558: [4, 4],
    3598562: [4],
    3598563: [4],
    3598564: [],
    3598740: [4, 4],
    3598746: [4],
    3598748: [4, 4],
    3598751: [4, 4],
    3598754: [4, 4],
    3598756: [4, 4],
    3598758: [4, 4],
    3598761: [4, 4],
    3598767: [4],
    3598769: [4, 4],
    3598771: [4],
    3598773: [4, 4],
    3598776: [4, 4],
    3598779: [1, 1],
    3598781: [1, 1],
    3598783: [4, 4],
    3598786: [4],
    3598788: [4, 4],
    3598792: [4],
    3598793: [4],
    3598794: [],
    3598971: [4, 4],
    3598974: [4],
    3598976: [4, 4],
    3598978: [4, 1],
    3598981: [4],
    3598983: [4, 4],
    3598985: [4, 4],
    3598987: [4, 4],
    3598990: [4, 4],
    3598993: [4, 4],
    3598996: [4],
    3598998: [4, 4],
    3599000: [4, 4],
    3599003: [4],
    3599005: [1, 1],
    3599007: [1, 1],
    3599009: [4],
    3599010: [4],
    3599011: [4],
    3599012: [4],
    3599014: [4, 4],
    3599021: [4, 4],
    3599024: [4, 4],
    3599028: [4],
    3599029: [4],
    3599030: [],
}


class ScalarCopyError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ScalarCopyError(message)


def _normalize(fn):
    try:
        return fn()
    except ScalarCopyError:
        raise
    except Exception as exc:
        raise ScalarCopyError(str(exc)) from exc


def _u32(value, label):
    _require(type(value) is int and 0 <= value <= U32, "invalid " + label)


def copy_spec(destination, source, length):
    for name, value in (
        ("destination", destination),
        ("source", source),
        ("length", length),
    ):
        _u32(value, name)
    _require(
        32 <= length <= 2048 and source + length <= U32 and destination + length <= U32,
        "outside bounded scalar nonwrapping copy domain",
    )
    direction = "backward" if source < destination < source + length else "forward"
    prefix = (
        ((destination + length) & 3)
        if direction == "backward"
        else ((-destination) & 3)
    )
    remaining = length - prefix
    remainder = remaining % 4
    flags = (
        small.copy_spec(destination, source, remaining)["arithmetic_flags"]
        if remaining < 32
        else (
            _logical(remainder)
            if direction == "forward"
            else _arithmetic(destination + remaining, 4, True)[1]
        )
    )
    return dict(
        direction=direction,
        length=length,
        destination=destination,
        source=source,
        prefix=prefix,
        remaining=remaining,
        remainder=remainder,
        arithmetic_flags=flags,
    )


def snapshot_spec(payload, base, destination, source, length):
    relation = copy_spec(destination, source, length)
    _u32(base, "payload base")
    _require(
        type(payload) is bytes and base + len(payload) <= U32, "invalid payload mapping"
    )
    _require(
        base <= source
        and source + length <= base + len(payload)
        and base <= destination
        and destination + length <= base + len(payload),
        "copy outside mapped buffer",
    )
    result = bytearray(payload)
    result[destination - base : destination - base + length] = payload[
        source - base : source - base + length
    ]
    edx = relation["remainder"]
    if relation["remaining"] < 32:
        edx = 0
        if relation["direction"] == "forward":
            at = (
                source
                - base
                + relation["prefix"]
                + 4 * (relation["remaining"] // 4 - 1)
            )
            edx = int.from_bytes(payload[at : at + 4], "little")
    return {"payload_after": bytes(result), "edx": edx, "relation": relation}


def _arithmetic(left, right, subtract):
    raw = left - right if subtract else left + right
    result = raw & U32
    overflow = (
        ((left ^ right) & (left ^ result)) >> 31
        if subtract
        else ((~(left ^ right)) & (left ^ result) & U32) >> 31
    )
    return result, {
        "cf": int(left < right) if subtract else int(raw > U32),
        "pf": int((result & 255).bit_count() % 2 == 0),
        "af": ((left ^ right ^ result) >> 4) & 1,
        "zf": int(result == 0),
        "sf": result >> 31,
        "of": overflow,
    }


def _logical(value):
    return {
        "cf": 0,
        "pf": int((value & 255).bit_count() % 2 == 0),
        "af": None,
        "zf": int(value == 0),
        "sf": value >> 31,
        "of": 0,
    }


def case_fixture(
    length, source_offset=2048, destination_offset=2049, frame_alignment=0, seed=1, df=0
):
    _require(
        type(source_offset) is int and type(destination_offset) is int,
        "invalid buffer offsets",
    )
    relation = copy_spec(PAYLOAD + destination_offset, PAYLOAD + source_offset, length)
    _require(
        0 <= source_offset <= 8192 - length
        and 0 <= destination_offset <= 8192 - length,
        "copy outside fixture payload",
    )
    _require(
        type(frame_alignment) is int and 0 <= frame_alignment < 16,
        "invalid frame alignment",
    )
    _u32(seed, "seed")
    _require(type(df) is int and df == 0, "invalid direction flag")
    stack = 0x30001000 + frame_alignment
    regs = {
        r: (0xA1000000 + i * 0x10101 + seed) & U32
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    regs["esp"] = stack
    payload = bytes(((i * 37) ^ (i >> 3) ^ seed) & 255 for i in range(8192))
    memory = {PAYLOAD + i: value for i, value in enumerate(payload)}
    memory.update({stack + i: ((i * 23) ^ seed) & 255 for i in range(-12, 20)})
    ret = (0x44556677 + seed) & U32
    for address, value in (
        (stack, ret),
        (stack + 4, relation["destination"]),
        (stack + 8, relation["source"]),
        (stack + 12, length),
    ):
        memory.update(
            {address + i: b for i, b in enumerate(value.to_bytes(4, "little"))}
        )
    for at, value in [(0x893F30, 0), (0x8B6E48, 0)] + [
        (BASE + table + 4 * i, BASE + target)
        for table, targets in TABLES.items()
        for i, target in enumerate(targets)
    ]:
        memory.update({at + i: b for i, b in enumerate(value.to_bytes(4, "little"))})
    return {
        "registers": regs,
        "memory": memory,
        "stack": stack,
        "payload": payload,
        "return_address": ret,
        "df": df,
    }


def model_case(
    length,
    source_offset=2048,
    destination_offset=2049,
    frame_alignment=0,
    seed=1,
    df=0,
    ops=None,
):
    fixture = case_fixture(
        length, source_offset, destination_offset, frame_alignment, seed, df
    )
    source, destination = PAYLOAD + source_offset, PAYLOAD + destination_offset
    expected = snapshot_spec(fixture["payload"], PAYLOAD, destination, source, length)
    initial = fixture["registers"]
    regs, memory = dict(initial), dict(fixture["memory"])
    operations = OPS if ops is None else ops
    flags = None
    pc = START
    returned = False
    return_address = None
    events, trace = [], []

    def access(address, width):
        _require(all(address + i in memory for i in range(width)), "unmapped copy read")
        value = int.from_bytes(
            bytes(memory[address + i] for i in range(width)), "little"
        )
        events.append(
            {"kind": "read", "address": address, "width": width, "value": value}
        )
        return value

    def address(arg):
        return (
            (regs[arg[1]] if arg[1] else 0)
            + arg[2]
            + (regs[arg[3]] * (arg[5] if len(arg) > 5 else 1) if arg[3] else 0)
        ) & U32

    def read(arg):
        if arg[0] == "reg":
            return regs["eax"] & 255 if arg[1] == "al" else regs[arg[1]]
        if arg[0] == "imm":
            return arg[1] & U32
        return access(address(arg), arg[4])

    def write(arg, value):
        if arg[0] == "reg":
            if arg[1] == "al":
                regs["eax"] = (regs["eax"] & 0xFFFFFF00) | (value & 255)
            else:
                regs[arg[1]] = value & U32
        else:
            at = address(arg)
            width = arg[4]
            _require(all(at + i in memory for i in range(width)), "unmapped copy write")
            memory.update(
                {at + i: b for i, b in enumerate(value.to_bytes(width, "little"))}
            )
            events.append(
                {"kind": "write", "address": at, "width": width, "value": value}
            )

    while not returned:
        _require(pc in operations and len(trace) < 250, "copy escaped scalar domain")
        trace.append(f"0x{pc:08x}")
        op, *args = operations[pc]
        next_pc = pc + SIZES[pc]
        if op == "push":
            value = read(args[0])
            regs["esp"] = (regs["esp"] - 4) & U32
            write(M("esp"), value)
        elif op == "pop":
            write(args[0], access(regs["esp"], 4))
            regs["esp"] = (regs["esp"] + 4) & U32
        elif op == "mov":
            write(args[0], read(args[1]))
        elif op == "lea":
            write(args[0], address(args[1]))
        elif op in ("add", "sub", "cmp", "inc", "dec"):
            left = read(args[0])
            right = read(args[1]) if len(args) > 1 else 1
            value, newflags = _arithmetic(left, right, op in ("sub", "cmp", "dec"))
            if op in ("inc", "dec"):
                newflags["cf"] = flags["cf"]
            flags = newflags
            if op != "cmp":
                write(args[0], value)
        elif op in ("and", "test", "xor"):
            value = (
                read(args[0]) ^ read(args[1])
                if op == "xor"
                else read(args[0]) & read(args[1])
            )
            flags = _logical(value)
            if op in ("and", "xor"):
                write(args[0], value)
        elif op == "shr":
            old = read(args[0])
            shift = read(args[1])
            value = old >> shift
            flags = _logical(value)
            flags.update(cf=(old >> (shift - 1)) & 1, af=None, of=None)
            write(args[0], value)
        elif op in ("jb", "jbe", "je", "jne", "jae"):
            take = (
                op == "jae"
                and not flags["cf"]
                or op == "jb"
                and flags["cf"]
                or op == "jbe"
                and (flags["cf"] or flags["zf"])
                or op == "je"
                and flags["zf"]
                or op == "jne"
                and not flags["zf"]
            )
            if take:
                next_pc = read(args[0]) - BASE
        elif op == "bt":
            flags = {k: None for k in ("cf", "pf", "af", "zf", "sf", "of")}
            flags["cf"] = (read(args[0]) >> read(args[1])) & 1
        elif op == "jmp":
            next_pc = read(args[0]) - BASE
        elif op in ("std", "cld"):
            df = int(op == "std")
        elif op == "rep movsd":
            while regs["ecx"]:
                write(M("edi"), access(regs["esi"], 4))
                step = -4 if df else 4
                regs["esi"] = (regs["esi"] + step) & U32
                regs["edi"] = (regs["edi"] + step) & U32
                regs["ecx"] -= 1
        elif op == "ret":
            return_address = access(regs["esp"], 4)
            regs["esp"] = (regs["esp"] + 4) & U32
            returned = True
        else:
            raise ScalarCopyError("unsupported scalar operation")
        pc = next_pc
    stack = fixture["stack"]
    wanted_memory = dict(fixture["memory"])
    wanted_events = []

    def expect(kind, at, width, value):
        wanted_events.append(
            {"kind": kind, "address": at, "width": width, "value": value}
        )
        if kind == "write":
            wanted_memory.update(
                {at + i: b for i, b in enumerate(value.to_bytes(width, "little"))}
            )

    expect("write", stack - 4, 4, initial["edi"])
    expect("write", stack - 8, 4, initial["esi"])
    expect("read", stack + 8, 4, source)
    expect("read", stack + 12, 4, length)
    expect("read", stack + 4, 4, destination)
    relation = expected["relation"]
    h, m = relation["prefix"], relation["remaining"]
    q, r = divmod(m, 4)
    backward = relation["direction"] == "backward"
    feature_reads = (
        [0x893F30]
        if backward or length < 128
        else [0x8B6E48]
        + ([0x893F30] if (source ^ destination) & 15 == 0 else [])
        + [0x8B6E48]
    )
    for at in feature_reads:
        expect("read", at, 4, 0)
    prefix = (
        [(length - 1 - i, 1) for i in range(h)]
        if backward
        else [(i, 1) for i in range(h)]
    )
    words = (
        [(m - 4 * (i + 1), 4) for i in range(q)]
        if backward
        else [(h + 4 * i, 4) for i in range(q)]
    )
    tail = (
        [(r - 1 - i, 1) for i in range(r)]
        if backward
        else [(h + 4 * q + i, 1) for i in range(r)]
    )
    spans = prefix + words + ([(-1, 0)] if m >= 32 else []) + tail
    for offset, width in spans:
        if width == 0:
            table = 0x36E890 if backward else 0x36E7E4
            expect("read", BASE + table + 4 * r, 4, BASE + TABLES[table][r])
            continue
        value = int.from_bytes(
            fixture["payload"][source_offset + offset : source_offset + offset + width],
            "little",
        )
        expect("read", source + offset, width, value)
        expect("write", destination + offset, width, value)
    expect("read", stack + 4, 4, destination)
    expect("read", stack - 8, 4, initial["esi"])
    expect("read", stack - 4, 4, initial["edi"])
    expect("read", stack, 4, fixture["return_address"])
    wanted_regs = dict(
        initial, eax=destination, ecx=0, edx=expected["edx"], esp=stack + 4
    )
    _require(
        regs == wanted_regs
        and flags == expected["relation"]["arithmetic_flags"]
        and df == fixture["df"],
        "copy register or flag relation differs",
    )
    _require(return_address == fixture["return_address"], "copy return target differs")
    _require(
        memory == wanted_memory and events == wanted_events,
        "ordered scalar copy relation differs",
    )
    actual_payload = bytes(memory[PAYLOAD + i] for i in range(8192))
    _require(
        actual_payload == expected["payload_after"], "independent snapshot copy differs"
    )
    return {
        "inputs": {
            "length": length,
            "source_offset": source_offset,
            "destination_offset": destination_offset,
            "frame_alignment": frame_alignment,
            "seed": seed,
            "df": df,
        },
        "direction": expected["relation"]["direction"],
        "registers": regs,
        "arithmetic_flags": flags,
        "df": df,
        "return_address": return_address,
        "events": events,
        "trace_rvas": trace,
        "payload_after_sha256": hashlib.sha256(actual_payload).hexdigest(),
    }


def _preflight(sources):
    _require(
        isinstance(sources, Mapping) and set(sources) == set(SOURCE_PINS),
        "source partition differs",
    )
    return {
        k: _source_identity(sources[k], kind, digest, k)
        for k, (kind, digest) in SOURCE_PINS.items()
    }


def _grammar(rows):
    _require(
        [r.address - BASE for r in rows] == ORDER,
        "scalar instruction partition differs",
    )
    for row in rows:
        args = []
        for arg in row.operands:
            if arg.type == x86.X86_OP_REG:
                args.append(R(row.reg_name(arg.reg)))
            elif arg.type == x86.X86_OP_IMM:
                args.append(I(arg.imm))
            elif arg.type == x86.X86_OP_MEM:
                _require(
                    arg.mem.segment
                    == (
                        x86.X86_REG_ES
                        if row.mnemonic == "rep movsd" and not args
                        else 0
                    ),
                    "unexpected memory segment",
                )
                args.append(
                    (
                        "mem",
                        row.reg_name(arg.mem.base) if arg.mem.base else None,
                        arg.mem.disp,
                        row.reg_name(arg.mem.index) if arg.mem.index else None,
                        arg.size,
                        arg.mem.scale,
                    )
                )
            else:
                raise ScalarCopyError("unexpected instruction operand")
        pc = row.address - BASE
        _require(
            (row.mnemonic, *args) == OPS[pc]
            and row.size == SIZES[pc]
            and [arg.size for arg in row.operands] == WIDTHS[pc],
            "exact scalar grammar differs",
        )


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(digest == EXE_SHA256 and image.image_base == BASE, "executable differs")
    facts = next(
        body
        for body in sources["program_facts"]["functions"]
        if int(body["entry_rva"], 16) == START
    )
    _require(
        [(int(r["start_rva"], 16), r["size"]) for r in facts["ranges"]]
        == list(FULL_RANGES),
        "copy range partition differs",
    )
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    rows = []
    chunks = []
    ranges = []
    for start, size in FULL_RANGES:
        offset = image.rva_to_file_offset(start)
        chunk = data[offset : offset + size]
        decoded = list(decoder.disasm(chunk, BASE + start))
        _require(sum(r.size for r in decoded) == size, "range contains undecoded bytes")
        rows.extend(decoded)
        chunks.append(chunk)
        ranges.append(
            {
                "start_rva": f"0x{start:08x}",
                "bytes": size,
                "nodes": len(decoded),
                "sha256": hashlib.sha256(chunk).hexdigest(),
                "points": [_point(r) for r in decoded],
            }
        )
    _require(
        len(rows) == 404
        and sum(len(c) for c in chunks) == facts["body_size"] == 1330
        and hashlib.sha256(b"".join(chunks)).hexdigest() == facts["body_sha256"],
        "full discontiguous copy witness differs",
    )
    scalar = [
        r for r in rows if any(a <= r.address - BASE < b for a, b in SCALAR_RANGES)
    ]
    _grammar(scalar)
    tables = []
    for start, targets in TABLES.items():
        offset = image.rva_to_file_offset(start)
        chunk = data[offset : offset + 16]
        actual = [
            int.from_bytes(chunk[i : i + 4], "little") - BASE for i in range(0, 16, 4)
        ]
        _require(
            actual == targets
            and all(start + 16 <= a or a + size <= start for a, size in FULL_RANGES),
            "excluded table bounds differ",
        )
        tables.append(
            {
                "start_rva": f"0x{start:08x}",
                "bytes": 16,
                "sha256": hashlib.sha256(chunk).hexdigest(),
                "target_rvas": [f"0x{target:08x}" for target in targets],
                "read_by_scalar_slice": True,
            }
        )
    _require(
        ranges == sources["small_copy_semantics"]["body"]["ranges"],
        "source full body witness differs",
    )
    lengths = [
        32,
        33,
        34,
        35,
        36,
        63,
        64,
        65,
        127,
        128,
        129,
        255,
        256,
        257,
        511,
        512,
        513,
        1023,
        1024,
        1025,
        2047,
        2048,
    ]
    deltas = [-2052, -17, -3, -1, 0, 1, 3, 17, 2052]
    cases = [
        model_case(n, 2052 + a, 2052 + a + delta, frame, seed, 0)
        for n in lengths
        for a in range(4)
        for delta in deltas
        for frame in (0, 15)
        for seed in (0, 255)
    ]
    union = sorted({p for c in cases for p in c["trace_rvas"]})
    _require(union == [f"0x{pc:08x}" for pc in ORDER], "scalar path coverage differs")
    controls = []
    for name, pc, replacement, args in [
        (
            "wrong_overlap_direction",
            0x36E59A,
            ("je", I(BASE + 0x36E834)),
            (128, 2052, 2053),
        ),
        ("wrong_rep_direction", 0x36E884, ("cld",), (128, 2052, 2053)),
        (
            "wrong_forward_prefix",
            0x36E7AF,
            ("mov", R("al"), M("esi", 1, width=1)),
            (64, 2052, 4105),
        ),
    ]:
        changed = dict(OPS)
        changed[pc] = replacement
        try:
            model_case(*args, ops=changed)
        except ScalarCopyError:
            controls.append(dict(name=name, rejected=True))
        else:
            raise ScalarCopyError("semantic mutation accepted")
    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": dict(sources["program_facts"]["identity"]),
        "source_receipts": ids,
        "body": {
            "entry_rva": f"0x{START:08x}",
            "bytes": 1330,
            "nodes": 404,
            "sha256": facts["body_sha256"],
            "ranges": ranges,
        },
        "scalar_ranges": [
            {
                "start_rva": f"0x{a:08x}",
                "exclusive_end_rva": f"0x{b:08x}",
                "bytes": b - a,
                "points": [_point(r) for r in scalar if a <= r.address - BASE < b],
            }
            for a, b in SCALAR_RANGES
        ],
        "tail_tables": tables,
        "matrix": {
            "lengths": lengths,
            "source_alignments": list(range(4)),
            "destination_deltas": deltas,
            "entry_stack_base": 0x30001000,
            "frame_alignments": [0, 15],
            "seeds": [0, 255],
            "direction_flags": [0],
        },
        "feature_premise": {"0x00493f30": 0, "0x004b6e48": 0},
        "model_evidence": {
            "cases_sha256": _canonical_sha256(cases),
            "instruction_union_rvas": union,
            "negative_controls": controls,
        },
        "summary": {
            "cases": len(cases),
            "static_bytes": 1330,
            "static_nodes": 404,
            "modeled_bytes": sum(SIZES[int(p, 16)] for p in union),
            "modeled_nodes": len(union),
            "forward_cases": sum(c["direction"] == "forward" for c in cases),
            "backward_cases": sum(c["direction"] == "backward" for c in cases),
            "actual_native_executions": 0,
            "calls": 0,
            "accounting_promotions": 0,
        },
        "scope": {
            "evidence_class": "bounded_feature_zero_scalar_rep_graph_with_snapshot_oracle",
            "premises": [
                "Length is 32 through 2048 and both exclusive buffer endpoints remain representable unsigned words",
                "Entry DF is zero and both named feature DWORDs are stable zero",
                "Mapped readable source and writable destination may overlap inside the fixed 8192 byte payload, disjoint from stable protected frame, code, feature words and tail tables",
                "Finite frame fixtures use base 0x30001000 and the listed alignments",
            ],
            "relation": "Destination equals original source snapshot and all other payload bytes remain unchanged; EAX returns destination, ECX is zero, ESI and EDI restore and DF returns zero",
            "flags": "Forward REP exits with remainder AND flags; backward REP preserves flags from subtracting four from the aligned destination end; short fallbacks retain their scalar arithmetic flags",
            "not_claimed": [
                "Other feature values, SIMD, REP MOVSB, larger lengths or arbitrary direction flag entry",
                "Actual native executions, full routine equivalence or global accounting promotion",
            ],
        },
    }
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "executable changed during build",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    def run():
        _validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256
            and evidence["source_receipts"] == ids,
            "sealed scalar copy differs",
        )
        _assert_publication_safe(evidence)
        return {
            "status": "structurally_verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(evidence["summary"]),
        }

    return _normalize(run)


def build_semantics(executable, sources):
    def run():
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_semantics(executable, evidence, sources):
    def run():
        validate_structure(evidence, sources)
        actual = build_semantics(executable, sources)
        _require(
            _canonical_bytes(actual) == _canonical_bytes(evidence),
            "exact scalar copy differs",
        )
        return {
            "status": "verified",
            "evidence_sha256": SEALED_SHA256,
            "summary": dict(actual["summary"]),
        }

    return _normalize(run)


def encode_semantics(value):
    return (
        json.dumps(
            dict(value), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )
