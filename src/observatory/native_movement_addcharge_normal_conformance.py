"""Continuous selected count-two AddCharge with supplied allocation and free successes.

The reviewed pure child laws are trusted. Native execution is continuous in one
machine between external API responses. Gameplay and ownership remain open.
"""

from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from src.observatory import native_assertion_helper_fill_conformance as common
from src.observatory import native_movement_addcharge_normal_semantics as model

BASE, EXE_SHA256 = common.BASE, common.EXE_SHA256
ANALYSIS_KIND = "pe_native_movement_addcharge_normal_conformance"
SEALED_SHA256 = "76ede8315ae9f10e431cf5038a140b1bd6fe055526dd8aae4913167794eae1ef"
POINTS_SHA256 = "75f7f7a59d22941340fb89c7d9bd5e17dfa4e520ba9c242e93ff87638f92cfb7"
SOURCE_PINS = dict(model.SOURCE_PINS)
BODY_PINS = dict(model.BODY_PINS)
BODIES = tuple(sorted((start, size) for start, (size, _) in BODY_PINS.items()))
REGISTERS, XMM = model.REGISTERS, model.XMM
RETURN, IMPORT, CPU_MODEL = 0x04000000, 0x05000000, 19
HEAP, HEAP_GLOBAL, ALLOC_IAT, FREE_IAT = 0x12345678, 0x8B7634, 0x7D6220, 0x7D621C
EXPECTED_KEYS = {
    "geometry",
    "path",
    "registers",
    "xmm",
    "pages",
    "events",
    "trace_rvas",
    "boundaries",
    "imports",
    "child_packets",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
}
FIXTURE_KEYS = {
    "pages",
    "registers",
    "xmm",
    "return_address",
    "entry_flags",
    "allocation_results",
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


def _same_packet(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return set(a) == set(b) and all(
            any(type(k) is type(j) and k == j for j in b) and _same_packet(a[k], b[k])
            for k in a
        )
    if type(a) in (list, tuple):
        return len(a) == len(b) and all(_same_packet(x, y) for x, y in zip(a, b))
    return a == b


def _read(pages, address, width=4):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(width)
    )


def _write(pages, address, payload):
    for i, v in enumerate(payload):
        pages[(address + i) & ~4095][(address + i) & 4095] = v


def _pages(pages):
    return {p: bytes(b) for p, b in pages.items()}


def _page_hashes(pages):
    return {
        f"0x{p:08x}": hashlib.sha256(b).hexdigest() for p, b in sorted(pages.items())
    }


def vectors():
    return [dict(alignment=a, profile=p) for a in range(16) for p in range(3)]


def _checked_vector(v):
    _require(
        type(v) is dict
        and set(v) == {"alignment", "profile"}
        and all(type(k) is str for k in v)
        and type(v["alignment"]) is int
        and 0 <= v["alignment"] < 16
        and type(v["profile"]) is int
        and 0 <= v["profile"] < 3,
        "normal AddCharge vector differs",
    )
    return v["alignment"], v["profile"]


def _fixture(vector):
    a, p = _checked_vector(vector)
    g, h, c, o = 0x30001000 + a, 0x10000100 + a, 0x10002000 + a, 0x06002FF9 + a
    results = [0x06001013 + a, 0x06001103 + a, 0x06002003 + a, 0x06003033 + a]
    page_keys = (
        0,
        0x30000000,
        0x30001000,
        0x10000000,
        0x10002000,
        0x06000000,
        0x06001000,
        0x06002000,
        0x06003000,
        0x00893000,
        0x0080D000,
        0x008B7000,
        0x007D6000,
    )
    pages = {
        pg: bytearray((i * 31 + j * 23 + a * 67 + p * 97) & 255 for j in range(4096))
        for i, pg in enumerate(page_keys)
    }
    cookie = (0x19A51C73, 0, 0xFFFFFFFF)[p]
    parameter = (0xBF800000, 0x7FC01234, 0x80000000)[p]
    seh = (0x1234ABCD, 0, 0xFFFFFFFF)[p]
    for at, v in (
        (g, RETURN),
        (g + 4, o),
        (g + 8, o + 16),
        (g + 12, o + 16),
        (g + 16, parameter),
        (h, c),
        (h + 4, c),
        (h + 8, c + 616),
        (0, seh),
        (model.COOKIE, cookie),
        (HEAP_GLOBAL, HEAP),
        (ALLOC_IAT, IMPORT),
        (FREE_IAT, IMPORT),
    ):
        _write(pages, at, v.to_bytes(4, "little"))
    _write(pages, model.move.LITERAL, b"\0")
    registers = {
        n: (0x12345678 + i * 0x11111111 + p * 0x31415927) & 0xFFFFFFFF
        for i, n in enumerate(REGISTERS)
    }
    registers.update(ecx=h, esp=g)
    xmm = {
        n: int.from_bytes(
            bytes((i * 19 + j * 41 + p * 71) & 255 for j in range(16)), "little"
        )
        for i, n in enumerate(XMM)
    }
    return dict(
        pages=_pages(pages),
        registers=registers,
        xmm=xmm,
        return_address=RETURN,
        entry_flags=(0x246, 0x287, 0x202)[p],
        allocation_results=results,
    )


def _replay(pages, events):
    memory = {p: bytearray(b) for p, b in pages.items()}
    for row in events:
        _require(
            type(row) is dict
            and set(row) == {"access", "address", "width", "value"}
            and type(row["access"]) is str
            and row["access"] in ("read", "write")
            and type(row["address"]) is int
            and 0 <= row["address"] < 2**32
            and type(row["width"]) is int
            and row["width"] in (1, 2, 4)
            and row["address"] + row["width"] <= 2**32
            and type(row["value"]) is int
            and 0 <= row["value"] < 2 ** (8 * row["width"]),
            "normal AddCharge replay schema differs",
        )
        payload = row["value"].to_bytes(row["width"], "little")
        if row["access"] == "read":
            _require(
                _read(memory, row["address"], row["width"]) == payload,
                "normal AddCharge replay read differs",
            )
        else:
            _write(memory, row["address"], payload)
    return _pages(memory)


def _add_flags(left, right):
    total = left + right
    result = total & 0xFFFFFFFF
    return (
        int(total > 0xFFFFFFFF)
        | (int((result & 255).bit_count() % 2 == 0) << 2)
        | (int(bool((left ^ right ^ result) & 16)) << 4)
        | (int(result == 0) << 6)
        | ((result >> 31) << 7)
        | (int(bool(~(left ^ right) & (left ^ result) & 0x80000000)) << 11)
    )


def _expected(vector, fixture):
    def run():
        _require(
            type(fixture) is dict
            and set(fixture) == FIXTURE_KEYS
            and all(type(k) is str for k in fixture)
            and _same_packet(fixture, _fixture(vector)),
            "normal AddCharge fixture differs",
        )
        result = model.apply(**fixture)
        _require(
            type(result) is dict
            and set(result) == EXPECTED_KEYS
            and all(type(k) is str for k in result),
            "normal AddCharge expected partition differs",
        )
        model.move._common_schema(result, set(fixture["pages"]))
        g = fixture["registers"]["esp"]
        h = fixture["registers"]["ecx"]
        c = int.from_bytes(_read(fixture["pages"], h + 4), "little")
        o = int.from_bytes(_read(fixture["pages"], g + 4), "little")
        parameter = int.from_bytes(_read(fixture["pages"], g + 16), "little")
        cookie = int.from_bytes(_read(fixture["pages"], model.COOKIE), "little")
        allocations = fixture["allocation_results"]
        _require(
            _same_packet(
                result["geometry"],
                dict(
                    entry=g,
                    receiver=h,
                    source_path=o,
                    argument_block=g - 40,
                    new_record=c,
                ),
            ),
            "normal AddCharge expected geometry differs",
        )
        _require(
            _same_packet(
                result["path"],
                dict(begin=o, end=o + 16, capacity=o + 16, parameter_bits=parameter),
            ),
            "normal AddCharge expected path differs",
        )
        _require(
            _same_packet(
                result["registers"],
                dict(
                    fixture["registers"],
                    eax=1,
                    ecx=cookie ^ (g - 4),
                    edx=0xB0000001,
                    esp=g + 20,
                ),
            )
            and _same_packet(result["xmm"], dict(fixture["xmm"], xmm0=parameter)),
            "normal AddCharge expected ABI differs",
        )
        _require(
            result["flags"] == _add_flags(g - 36, 12)
            and result["flag_mask"] == 0x8D5
            and type(result["df"]) is int
            and result["df"] == 0
            and type(result["endpoint"]) is int
            and result["endpoint"] == RETURN,
            "normal AddCharge expected endpoint differs",
        )
        _require(
            len(result["trace_rvas"]) == 2303
            and len(result["events"]) == 1426
            and type(result["boundaries"]) is list
            and len(result["boundaries"]) == 6
            and type(result["imports"]) is list
            and len(result["imports"]) == 8
            and type(result["child_packets"]) is dict
            and set(result["child_packets"])
            == {"clone_argument", "addmove", "free_original"},
            "normal AddCharge expected count differs",
        )
        _require(
            _same_packet(_replay(fixture["pages"], result["events"]), result["pages"]),
            "normal AddCharge expected replay differs",
        )
        common_keys = {
            "registers",
            "xmm",
            "pages",
            "events",
            "flags",
            "flag_mask",
            "df",
            "endpoint",
        }
        names = ("clone_argument", "addmove", "free_original")
        import_names = (
            "clone_argument",
            "assignment",
            "record_copy",
            "append",
            "destroy_temp",
            "destroy_original",
            "free_caller",
            "free_original",
        )
        for index, state in enumerate(result["boundaries"]):
            _require(
                type(state) is dict
                and set(state) == common_keys | {"name", "phase"}
                and all(type(k) is str for k in state)
                and type(state["name"]) is str
                and state["name"] == names[index // 2]
                and type(state["phase"]) is str
                and state["phase"] == ("entry", "return")[index % 2],
                "normal AddCharge boundary schema differs",
            )
        for index, state in enumerate(result["imports"]):
            _require(
                type(state) is dict
                and set(state) == common_keys | {"name", "entry_esp", "words"}
                and all(type(k) is str for k in state)
                and type(state["name"]) is str
                and state["name"] == import_names[index]
                and type(state["entry_esp"]) is int
                and 0 <= state["entry_esp"] < 2**32
                and state["entry_esp"] == state["registers"]["esp"]
                and type(state["words"]) is list
                and len(state["words"]) == 4
                and all(type(v) is int and 0 <= v < 2**32 for v in state["words"])
                and state["endpoint"] == IMPORT,
                "normal AddCharge import schema differs",
            )
        extras = {
            "clone_argument": {
                "geometry",
                "boundaries",
                "allocation_packet",
                "scalar_packet",
                "imported",
                "source_snapshot",
            },
            "addmove": {"geometry", "path", "boundaries", "imports", "child_packets"},
        }
        for index, (name, extra) in enumerate(extras.items()):
            child = result["child_packets"][name]
            _require(
                type(child) is dict
                and set(child) == common_keys | {"trace_rvas"} | extra
                and all(type(k) is str for k in child)
                and type(child["df"]) is int
                and child["df"] == 0
                and type(child["endpoint"]) is int
                and child["endpoint"]
                == result["boundaries"][2 * index + 1]["endpoint"],
                "normal AddCharge child schema differs",
            )
            model.move._common_schema(child, set(fixture["pages"]))
        free = result["child_packets"]["free_original"]
        _require(
            type(free) is dict
            and set(free)
            == {
                "registers",
                "flags",
                "flag_mask",
                "events",
                "stack",
                "error",
                "stop",
                "protocol",
            }
            and all(type(k) is str for k in free)
            and type(free["registers"]) is dict
            and set(free["registers"]) == set(REGISTERS)
            and all(
                type(k) is str and type(v) is int and 0 <= v < 2**32
                for k, v in free["registers"].items()
            )
            and type(free["flags"]) is int
            and free["flags"] & ~0x8D5 == 0
            and type(free["flag_mask"]) is int
            and free["flag_mask"] == 0x8D5
            and type(free["events"]) is list
            and len(free["events"]) == 20
            and type(free["stack"]) is bytes
            and len(free["stack"]) == 8192
            and type(free["error"]) is bytes
            and len(free["error"]) == 4096
            and type(free["stop"]) is int
            and free["stop"] == BASE + 0x257765
            and _same_packet(
                free["protocol"],
                dict(
                    returned=True,
                    result=1,
                    next_kind=None,
                    error_cell=None,
                    last_error=None,
                ),
            ),
            "normal AddCharge free child schema differs",
        )
        free_entry, free_return = result["boundaries"][4:6]
        base = min((g - 72) & ~4095, 0xFFFFE000)
        _require(
            _same_packet(free["registers"], free_return["registers"])
            and _same_packet(free["flags"], free_return["flags"])
            and _same_packet(
                free["events"],
                result["events"][
                    len(free_entry["events"]) : len(free_return["events"])
                ],
            )
            and _same_packet(
                _replay(free_entry["pages"], free["events"]), free_return["pages"]
            )
            and free["stack"] == _read(free_return["pages"], base, 8192)
            and free["error"] == free_return["pages"][model.ERROR],
            "normal AddCharge free child state differs",
        )
        for state in result["boundaries"] + result["imports"]:
            _require(
                type(state) is dict
                and type(state["events"]) is list
                and _same_packet(
                    state["events"], result["events"][: len(state["events"])]
                )
                and _same_packet(
                    _replay(fixture["pages"], state["events"]), state["pages"]
                ),
                "normal AddCharge expected prefix differs",
            )
            _require(
                type(state["registers"]) is dict
                and set(state["registers"]) == set(REGISTERS)
                and all(type(k) is str for k in state["registers"])
                and all(
                    type(v) is int and 0 <= v < 2**32
                    for v in state["registers"].values()
                )
                and type(state["xmm"]) is dict
                and set(state["xmm"]) == set(XMM)
                and all(type(k) is str for k in state["xmm"])
                and all(
                    type(v) is int and 0 <= v < 2**128 for v in state["xmm"].values()
                )
                and type(state["flags"]) is int
                and type(state["flag_mask"]) is int
                and state["flag_mask"] in (0x8D5, 0x8C5, 0xC5)
                and state["flags"] & ~state["flag_mask"] == 0
                and type(state["df"]) is int
                and state["df"] == 0
                and type(state["endpoint"]) is int
                and 0 <= state["endpoint"] < 2**32,
                "normal AddCharge expected state schema differs",
            )
        _require(
            [len(row["events"]) for row in result["boundaries"]]
            == [15, 98, 99, 1392, 1400, 1420],
            "normal AddCharge primary event partition differs",
        )
        _require(
            [row["endpoint"] for row in result["boundaries"]]
            == [
                BASE + pc
                for pc in (0x9A8E0, 0x257738, 0x257340, 0x25773F, 0x7800, 0x257765)
            ]
            and [row["words"] for row in result["imports"]]
            == [[BASE + 0x389463, HEAP, 0, 16]] * 4
            + [
                [BASE + 0x389172, HEAP, 0, pointer]
                for pointer in (allocations[2], allocations[1], allocations[0], o)
            ],
            "normal AddCharge installed call partition differs",
        )
        for index, name in enumerate(("clone_argument", "addmove")):
            child = result["child_packets"][name]
            before, after = result["boundaries"][2 * index : 2 * index + 2]
            _require(
                _same_packet(
                    child["events"],
                    result["events"][len(before["events"]) : len(after["events"])],
                )
                and all(
                    _same_packet(child[key], after[key])
                    for key in (
                        "registers",
                        "xmm",
                        "pages",
                        "flags",
                        "flag_mask",
                        "df",
                        "endpoint",
                    )
                )
                and len(child["trace_rvas"]) == (136, 2089)[index],
                "normal AddCharge child return differs",
            )
        final = result["pages"]
        _require(
            _read(final, h, 4) == _read(fixture["pages"], h, 4)
            and int.from_bytes(_read(final, h + 4), "little") == c + 308
            and _read(final, h + 8) == _read(fixture["pages"], h + 8)
            and int.from_bytes(_read(final, c + 0xD8), "little") == 2
            and int.from_bytes(_read(final, c + 0xC8), "little") == parameter
            and _read(final, c + 0xCC, 12)
            == b"".join(
                v.to_bytes(4, "little")
                for v in (allocations[3], allocations[3] + 16, allocations[3] + 16)
            )
            and all(
                _read(final, d, 16) == _read(fixture["pages"], o, 16)
                for d in allocations
            )
            and _read(final, o, 16) == _read(fixture["pages"], o, 16),
            "normal AddCharge expected record differs",
        )
        _require(
            _read(final, g, 16) == _read(fixture["pages"], g, 16)
            and int.from_bytes(_read(final, g + 16), "little") == g - 40,
            "normal AddCharge caller words differ",
        )
        return result

    return _normalize(run)


def _preflight(sources):
    def run():
        _require(
            type(sources) is dict and set(sources) == set(SOURCE_PINS),
            "normal AddCharge source partition differs",
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
            "normal AddCharge source build differs",
        )
        atlas = {
            int(row["entry_rva"], 16): row
            for row in sources["program_facts"]["functions"]
        }
        _require(
            len(atlas) == len(sources["program_facts"]["functions"]),
            "normal AddCharge duplicate atlas entry",
        )
        for start, (size, digest) in BODY_PINS.items():
            row = atlas[start]
            _require(
                type(row["body_size"]) is int
                and row["body_size"] == size
                and row["body_sha256"] == digest
                and row["ranges"] == [dict(start_rva=f"0x{start:08x}", size=size)],
                "normal AddCharge atlas body differs",
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
            "normal AddCharge direct code identity differs",
        )
        _require(
            points == sorted(points, key=lambda p: int(p["rva"], 16)),
            "normal AddCharge direct point order differs",
        )
        allowed = {}
        for start, size in BODIES:
            _require(
                type(codes[start]) is bytes
                and len(codes[start]) == size
                and hashlib.sha256(codes[start]).hexdigest() == BODY_PINS[start][1],
                "normal AddCharge direct body differs",
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
                    "normal AddCharge direct point differs",
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
                    "normal AddCharge direct bytes differ",
                )
                allowed[pc] = point
                cursor += point["size"]
            _require(cursor == start + size, "normal AddCharge direct extent differs")
        _require(
            len(allowed) == len(points) == 1252,
            "normal AddCharge direct partition differs",
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
            "normal AddCharge executable differs",
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


STATE_ROLES = (
    ("outer_entry",)
    + tuple(f"boundary_{i:02}" for i in range(6))
    + tuple(f"import_{i:02}" for i in range(8))
    + ("outer_return",)
)
CONTROLS = {
    f"{role}_{kind}": dict(
        role=role, kind=kind, reason=f"native state differs at {role} in {kind}"
    )
    for role in STATE_ROLES
    for kind in ("gpr", "xmm", "pages", "flags", "df")
}


def _run_case(codes, points, vector, negative=None, *, capture=None):
    def run():
        allowed = _checked_code_packet(codes, points)
        fixture = _fixture(vector)
        expected = _expected(vector, fixture)
        _require(
            negative is None or type(negative) is str and negative in CONTROLS,
            "normal AddCharge unknown control",
        )
        import unicorn as u
        from unicorn import x86_const as x

        machine = u.Uc(u.UC_ARCH_X86, u.UC_MODE_32)
        machine.ctl_set_cpu_model(CPU_MODEL)
        code_pages = {RETURN, IMPORT} | {
            at & ~4095
            for start, code in codes.items()
            for at in range(BASE + start, BASE + start + len(code))
        }
        _require(
            not code_pages.intersection(fixture["pages"]),
            "normal AddCharge code/data collision",
        )
        for page in sorted(code_pages):
            machine.mem_map(page, 4096)
            machine.mem_write(page, bytes([0xCC]) * 4096)
        for start, body in codes.items():
            machine.mem_write(BASE + start, body)
        for page, data in fixture["pages"].items():
            machine.mem_map(page, 4096)
            machine.mem_write(page, data)
        ids = {n: getattr(x, "UC_X86_REG_" + n.upper()) for n in REGISTERS}
        xi = {n: getattr(x, "UC_X86_REG_" + n.upper()) for n in XMM}
        for n, v in fixture["registers"].items():
            machine.reg_write(ids[n], v)
        for n, v in fixture["xmm"].items():
            machine.reg_write(xi[n], v)
        machine.reg_write(x.UC_X86_REG_EFLAGS, fixture["entry_flags"])
        events = []
        trace = []
        api = []
        states = []
        cursor = 0
        resume = None
        control_used = False
        outer_seen = False

        def state_check(role, state):
            nonlocal control_used
            if negative is not None and CONTROLS[negative]["role"] == role:
                _require(not control_used, "normal AddCharge repeated control")
                kind = CONTROLS[negative]["kind"]
                if kind == "gpr":
                    machine.reg_write(ids["eax"], machine.reg_read(ids["eax"]) ^ 1)
                elif kind == "xmm":
                    machine.reg_write(xi["xmm0"], machine.reg_read(xi["xmm0"]) ^ 1)
                elif kind == "pages":
                    pg = min(fixture["pages"])
                    machine.mem_write(
                        pg + 0x800,
                        bytes(
                            [
                                int.from_bytes(
                                    machine.mem_read(pg + 0x800, 1), "little"
                                )
                                ^ 1
                            ]
                        ),
                    )
                elif kind == "flags":
                    machine.reg_write(
                        x.UC_X86_REG_EFLAGS, machine.reg_read(x.UC_X86_REG_EFLAGS) ^ 1
                    )
                elif kind == "df":
                    machine.reg_write(
                        x.UC_X86_REG_EFLAGS,
                        machine.reg_read(x.UC_X86_REG_EFLAGS) ^ 0x400,
                    )
                control_used = True
            _require(
                _same_packet(
                    {n: machine.reg_read(i) for n, i in ids.items()}, state["registers"]
                ),
                f"native state differs at {role} in gpr",
            )
            _require(
                _same_packet(
                    {n: machine.reg_read(i) for n, i in xi.items()}, state["xmm"]
                ),
                f"native state differs at {role} in xmm",
            )
            _require(
                all(
                    bytes(machine.mem_read(pg, 4096)) == raw
                    for pg, raw in state["pages"].items()
                ),
                f"native state differs at {role} in pages",
            )
            _require(
                machine.reg_read(x.UC_X86_REG_EFLAGS) & state["flag_mask"]
                == state["flags"],
                f"native state differs at {role} in flags",
            )
            _require(
                machine.reg_read(x.UC_X86_REG_EFLAGS) & 0x400 == 0,
                f"native state differs at {role} in df",
            )
            _require(events == state["events"], f"native event order differs: {role}")
            _require(
                machine.reg_read(x.UC_X86_REG_EIP) == state["endpoint"],
                f"native endpoint differs: {role}",
            )
            states.append(
                dict(
                    role=role,
                    event_prefix=len(events),
                    registers=dict(state["registers"]),
                    xmm={n: f"0x{v:032x}" for n, v in state["xmm"].items()},
                    flags=state["flags"],
                    flag_mask=state["flag_mask"],
                    endpoint=f"0x{state['endpoint']:08x}",
                    pages_sha256=_page_hashes(state["pages"]),
                )
            )

        def code_hook(m, at, size, user):
            nonlocal cursor, resume, outer_seen
            if at == RETURN:
                state_check("outer_return", expected)
                m.emu_stop()
                return
            if not outer_seen:
                _require(at == BASE + 0x2576F0, "normal AddCharge entry differs")
                state_check(
                    "outer_entry",
                    dict(
                        registers=fixture["registers"],
                        xmm=fixture["xmm"],
                        pages=fixture["pages"],
                        events=[],
                        flags=fixture["entry_flags"] & 0x8D5,
                        flag_mask=0x8D5,
                        endpoint=BASE + 0x2576F0,
                    ),
                )
                outer_seen = True
            if at == IMPORT:
                index = len(api)
                _require(index < 8, "normal AddCharge extra import")
                state = expected["imports"][index]
                state_check(f"import_{index:02}", state)
                sp = m.reg_read(ids["esp"])
                words = [
                    int.from_bytes(m.mem_read(sp + 4 * i, 4), "little")
                    for i in range(4)
                ]
                _require(
                    _same_packet(words, state["words"])
                    and words[1] == HEAP
                    and words[2] == 0,
                    "normal AddCharge imported words differ",
                )
                if index < 4:
                    _require(
                        words[0] == BASE + 0x389463 and words[3] == 16,
                        "normal AddCharge allocation request differs",
                    )
                    result = fixture["allocation_results"][index]
                    kind = "allocate"
                else:
                    _require(
                        words[0] == BASE + 0x389172
                        and words[3]
                        == [
                            fixture["allocation_results"][2],
                            fixture["allocation_results"][1],
                            fixture["allocation_results"][0],
                            expected["path"]["begin"],
                        ][index - 4],
                        "normal AddCharge free request differs",
                    )
                    result = 1
                    kind = "free"
                before_pages = {
                    pg: bytes(m.mem_read(pg, 4096)) for pg in fixture["pages"]
                }
                before_registers = {n: m.reg_read(i) for n, i in ids.items()}
                before_xmm = {n: m.reg_read(i) for n, i in xi.items()}
                for n, v in (
                    ("eax", result),
                    ("ecx", 0xA0000001),
                    ("edx", 0xB0000001),
                    ("esp", sp + 16),
                ):
                    m.reg_write(ids[n], v)
                m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
                _require(
                    all(
                        bytes(m.mem_read(pg, 4096)) == raw
                        for pg, raw in before_pages.items()
                    )
                    and {n: m.reg_read(i) for n, i in xi.items()} == before_xmm
                    and {n: m.reg_read(ids[n]) for n in ("ebx", "esi", "edi", "ebp")}
                    == {n: before_registers[n] for n in ("ebx", "esi", "edi", "ebp")},
                    "normal AddCharge response preservation differs",
                )
                api.append(
                    dict(
                        kind=kind,
                        entry_esp=sp,
                        words=words,
                        result=result,
                        event_prefix=len(events),
                    )
                )
                resume = words[0]
                m.emu_stop()
                return
            _require(
                at - BASE in allowed and size == allowed[at - BASE]["size"],
                "normal AddCharge unexpected instruction",
            )
            if cursor < 6 and at == expected["boundaries"][cursor]["endpoint"]:
                state_check(f"boundary_{cursor:02}", expected["boundaries"][cursor])
                cursor += 1
            trace.append(f"0x{at-BASE:08x}")

        def memory_hook(m, access, at, width, value, user):
            writing = access == u.UC_MEM_WRITE
            events.append(
                dict(
                    access="write" if writing else "read",
                    address=at,
                    width=width,
                    value=(
                        value & ((1 << (8 * width)) - 1)
                        if writing
                        else int.from_bytes(m.mem_read(at, width), "little")
                    ),
                )
            )

        machine.hook_add(u.UC_HOOK_CODE, code_hook)
        machine.hook_add(u.UC_HOOK_MEM_READ | u.UC_HOOK_MEM_WRITE, memory_hook)
        machine.emu_start(BASE + 0x2576F0, 0, count=20000)
        starts = 1
        while machine.reg_read(x.UC_X86_REG_EIP) != RETURN:
            _require(
                resume is not None and starts <= 8,
                "normal AddCharge failed continuation",
            )
            at = resume
            resume = None
            starts += 1
            machine.emu_start(at, 0, count=20000)
        _require(
            cursor == 6
            and len(api) == 8
            and len(states) == 16
            and starts == 9
            and trace == expected["trace_rvas"]
            and len(events) == 1426,
            "normal AddCharge final execution differs",
        )
        _require(negative is None, "normal AddCharge control not rejected")
        observation = dict(
            vector=copy.deepcopy(vector),
            instructions=len(trace),
            memory_events=len(events),
            boundary_states=len(states),
            api_calls=api,
            trace_sha256=_canonical_sha256(trace),
            events_sha256=_canonical_sha256(events),
            states_sha256=_canonical_sha256(states),
            final_registers=dict(expected["registers"]),
            final_xmm={n: f"0x{v:032x}" for n, v in expected["xmm"].items()},
            flags=expected["flags"],
            flag_mask=expected["flag_mask"],
            df=0,
            endpoint=f"0x{RETURN:08x}",
            pages_sha256=_page_hashes(expected["pages"]),
            loaded_sites=len(points),
            executed_sites=sorted(set(trace)),
        )
        if capture is not None:
            capture(machine, dict(ids), copy.deepcopy(expected), copy.deepcopy(fixture))
        return observation

    return _normalize(run)


def _build_unsealed(executable, sources):
    def run():
        identities = _preflight(sources)
        data, image, digest = common._load_executable(Path(executable))
        _require(digest == EXE_SHA256, "normal AddCharge executable hash differs")
        codes, points = _load_code(data, image, sources)
        cases = [_run_case(codes, points, v) for v in vectors()]
        controls = []
        vector = dict(alignment=15, profile=2)
        for name, control in CONTROLS.items():
            try:
                _run_case(codes, points, vector, name)
            except ConformanceError as exc:
                _require(
                    str(exc) == control["reason"],
                    f"normal AddCharge wrong control reason: {name}: {exc}",
                )
                controls.append(dict(name=name, reason=str(exc), rejected=True))
            else:
                raise ConformanceError(f"normal AddCharge control accepted: {name}")
        executed = sorted(set(pc for case in cases for pc in case["executed_sites"]))
        result = dict(
            analysis_kind=ANALYSIS_KIND,
            build_identity=copy.deepcopy(sources["program_facts"]["identity"]),
            sources=identities,
            method=dict(
                machine="x86-32",
                cpu_model=CPU_MODEL,
                continuous=True,
                machines_per_case=1,
                starts_per_case=9,
                external_responses_per_case=8,
                expected_model="reviewed selected count-two AddCharge",
                typed_replay=True,
                universal_coordinated_forgery_rejection=False,
            ),
            bodies=[
                dict(entry_rva=f"0x{s:08x}", size=z, sha256=BODY_PINS[s][1])
                for s, z in BODIES
            ],
            instruction_points=points,
            cases=cases,
            negative_controls=controls,
            summary=dict(
                cases=48,
                negative_controls=len(CONTROLS),
                loaded_bodies=len(BODIES),
                loaded_bytes=sum(z for _, z in BODIES),
                loaded_instruction_sites=len(points),
                executed_instruction_sites=len(executed),
                executed_instructions=sum(c["instructions"] for c in cases),
                memory_events=sum(c["memory_events"] for c in cases),
                boundary_states=sum(c["boundary_states"] for c in cases),
                allocation_requests=192,
                allocation_requested_bytes=3072,
                allocation_responses=192,
                free_requests=192,
                free_responses=192,
                path_copied_bytes=3072,
                appended_records=48,
                receiver_advanced_bytes=14784,
                cookie_checks=48,
                opaque_callees=0,
                wide_copies=0,
                accounting_delta=0,
            ),
            scope=dict(
                selected="two-entry owned source path, eight inline-empty strings, existing receiver capacity, ordinary successful allocation and free",
                unresolved=[
                    "other path counts",
                    "nonempty strings",
                    "receiver growth",
                    "allocation and free failure",
                    "exception unwinding",
                    "ownership",
                    "Lua execution",
                    "pawn movement",
                    "whole game",
                ],
            ),
        )
        common._assert_publication_safe(result)
        return result

    return _normalize(run)


def validate_structure(evidence, sources):
    def run():
        _preflight(sources)
        common._validate_json_tree(evidence, "evidence")
        common._assert_publication_safe(evidence)
        _require(
            type(evidence) is dict
            and evidence.get("analysis_kind") == ANALYSIS_KIND
            and _same_packet(
                evidence.get("build_identity"), sources["program_facts"]["identity"]
            )
            and _same_packet(evidence.get("sources"), _preflight(sources)),
            "normal AddCharge evidence identity differs",
        )
        _require(
            SEALED_SHA256 != "PENDING" and _canonical_sha256(evidence) == SEALED_SHA256,
            "normal AddCharge evidence seal differs",
        )
        return copy.deepcopy(evidence)

    return _normalize(run)


def build_conformance(executable, sources):
    result = _build_unsealed(executable, sources)
    _require(
        SEALED_SHA256 != "PENDING" and _canonical_sha256(result) == SEALED_SHA256,
        "normal AddCharge fresh evidence seal differs",
    )
    return result


def validate_conformance(executable, evidence, sources):
    result = validate_structure(evidence, sources)
    _require(
        _same_packet(result, build_conformance(executable, sources)),
        "normal AddCharge recomputed evidence differs",
    )
    return result


def encode_conformance(value):
    common._validate_json_tree(value, "evidence")
    common._assert_publication_safe(value)
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
