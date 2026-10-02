"""Independent continuous clone2 pages, ABI, allocation and scalar joins.

Production expectations are actuals only. Oracle follows decoded owner operands,
ordinary allocation instructions, and the separate handwritten scalar test law.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "src/observatory").is_dir()
)
sys.path.insert(0, str(ROOT))
from src.observatory import native_movement_path_clone2_conformance as c
from tests import test_itb_native_movement_path_scalar_clone2_semantics as p

PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE = PROGRAMS / (PREFIX + "native_movement_path_clone2_conformance.json")
CLI = ROOT / "scripts/itb_native_movement_path_clone2_conformance.py"
SOURCE_PINS = {
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
    "movement_binding": (
        "pe_native_movement_effect_binding",
        "54c060913d61f6bb5e4c1f2586f0d5186ea73ad6c058dd48b1cc056e64a410b9",
    ),
    "allocation_composition": (
        "pe_native_vector_allocation_composition",
        "a63d7ef54e07f8aa63449136988a237592704708ab35cbefb203ec843e8e5507",
    ),
    "allocation_conformance": (
        "pe_native_vector_allocation_conformance",
        "8a2af8e009d4f67b672e92e9fd12bce6a5c32feb609af95f2ee1dc61fb1e9d29",
    ),
}
OBS_KEYS = {
    "vector",
    "registers",
    "xmm",
    "flags",
    "flag_mask",
    "df",
    "trace_rvas",
    "events_sha256",
    "pages_sha256",
    "memory_event_count",
    "boundaries",
    "summaries",
}
BOUNDARY_KEYS = {
    "name",
    "registers",
    "xmm",
    "eflags",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "pages_sha256",
    "events_sha256",
}
PACKET_KEYS = {
    "geometry",
    "registers",
    "xmm",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "pages",
    "events",
    "trace_rvas",
    "boundaries",
    "allocation_packet",
    "scalar_packet",
    "imported",
    "source_snapshot",
}
PARENT_BEFORE = tuple(
    int(w, 16)
    for w in "9a8e0 9a8e1 9a8e3 9a8e4 9a8e6 9a8e7 9a8ea 9a8f0 9a8f7 9a8fe 9a901 9a903 9a906 9a907".split()
)
RESERVE_BEFORE = tuple(
    int(w, 16)
    for w in "9ac40 9ac41 9ac43 9ac44 9ac46 9ac47 9ac4a 9ac50 9ac57 9ac5e 9ac60 9ac6a 9ac70 9ac72 9ac73".split()
)
ALLOCATION = tuple(int(w, 16) for w in """
8a920 8a921 8a923 8a926 8a928 8a932 8a937 8a939 8a93c 8a941 8a962 8a963
3574db 3574dc 3574de 3574ff 357502 379f52 379f54 379f55 379f57 379f58
38942b 38942d 38942e 389430 389431 389434 389437 389439 38943b 389454
389455 389457 38945d 389463 389465 389467 389476 389477 389478
357507 357508 35750a 35750c 35750d 8a968 8a96b 8a96d 8a96e
""".split())
RESERVE_AFTER = tuple(
    int(w, 16)
    for w in "9ac78 9ac7a 9ac7d 9ac7f 9ac82 9ac85 9ac87 9ac88 9ac89 9ac8a".split()
)
PARENT_MIDDLE = tuple(
    int(w, 16) for w in "9a90c 9a90e 9a910 9a913 9a914 9a917 9a918 9a91a 9a91c".split()
)
PARENT_AFTER = tuple(
    int(w, 16) for w in "9a921 9a924 9a927 9a928 9a92a 9a92b 9a92c".split()
)
TRACE = (
    PARENT_BEFORE
    + RESERVE_BEFORE
    + ALLOCATION
    + RESERVE_AFTER
    + PARENT_MIDDLE
    + p.TRACE
    + PARENT_AFTER
)
CONTROL_REASONS = {
    **{
        stage + "_" + kind: "path clone2 " + stage.replace("_", " ") + " differs"
        for stage in (
            "parent_entry",
            "reserve_entry",
            "allocation_entry",
            "allocation_return",
            "reserve_return",
            "scalar_entry",
            "scalar_return",
        )
        for kind in ("gpr", "xmm", "flags", "df", "page")
    },
    "reserve_full_eax": "path clone2 reserve return differs",
    "heap_request": "path clone2 allocation handoff differs",
    **{
        name: "path clone2 supplied response preservation differs"
        for name in ("response_result", "response_gpr", "response_xmm", "response_page")
    },
    **{
        name: "path clone2 final pages differ"
        for name in (
            "ancestor",
            "source",
            "source_header",
            "destination",
            "header_padding",
            "feature_padding",
            "iat_padding",
            "unused_scalar_word",
        )
    },
    **{
        name: "path clone2 final ABI differs"
        for name in (
            "final_eax",
            "final_nonvolatile",
            "final_xmm",
            "final_flags",
            "final_df",
            "final_endpoint",
        )
    },
    **{
        name: "path clone2 final events differ"
        for name in (
            "missing_read_record",
            "restored_write_record",
            "duplicate_write_record",
        )
    },
    "trace_record": "path clone2 final native path differs",
}


def canonical(value):
    return hashlib.sha256(
        (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode()
    ).hexdigest()


def page_hashes(pages):
    return {
        f"0x{base:08x}": hashlib.sha256(data).hexdigest()
        for base, data in sorted(pages.items())
    }


def recipes():
    return [dict(alignment=a, profile=i) for a in range(16) for i in range(3)]


def finite_fixture(vector):
    a, i = vector["alignment"], vector["profile"]
    frame, source, dest, j, h = (
        0x30001000 + a,
        0x6002800 + a,
        0x6001000 + a,
        0x10000080 + a,
        0x10000100 + a,
    )
    bases = (
        0x30000000,
        0x30001000,
        0x6000000,
        0x6001000,
        0x6002000,
        0x6003000,
        0x10000000,
        0x893000,
        0x8B7000,
        0x7D6000,
    )
    pages = {
        base: bytes((n * 37 + offset * 13 + i * 71) & 255 for offset in range(4096))
        for n, base in enumerate(bases)
    }
    for at, word in (
        (frame, 0x4000000),
        (frame + 4, j),
        (j, source),
        (j + 4, source + 16),
        (j + 8, source + 16),
        (0x8B7634, 0x12345678),
        (0x7D6220, 0x5000000),
    ):
        p.store(pages, at, word)
    for n, word in enumerate((0xD15C0016, 0x1234AA16, 0xF00D0016, 0x8765DD16)):
        p.store(pages, source + n * 4, (word ^ (i * 0x7654321)) & 0xFFFFFFFF)
    regs = {
        name: (0x12345678 + n * 0x11111111 + i * 0x1234) & 0xFFFFFFFF
        for n, name in enumerate(p.GPRS)
    }
    regs.update(ecx=h, esp=frame)
    xmm = {
        name: int.from_bytes(
            bytes((n * 19 + j * 41 + i * 73) & 255 for j in range(16)), "little"
        )
        for n, name in enumerate(p.XMMS)
    }
    return dict(
        pages=pages,
        registers=regs,
        xmm=xmm,
        return_address=0x4000000,
        entry_flags=0x246,
    )


def add_flags(left, right):
    result = (left + right) & 0xFFFFFFFF
    return (
        int(left + right > 0xFFFFFFFF)
        | (4 if (result & 255).bit_count() % 2 == 0 else 0)
        | (0x10 if (left ^ right ^ result) & 0x10 else 0)
        | (0x40 if result == 0 else 0)
        | (0x80 if result & 0x80000000 else 0)
        | (0x800 if (~(left ^ right) & (left ^ result)) & 0x80000000 else 0)
    )


def independent(vector, fixture):
    a = vector["alignment"]
    frame, o, d, j, h = (
        0x30001000 + a,
        0x6002800 + a,
        0x6001000 + a,
        0x10000080 + a,
        0x10000100 + a,
    )
    pages = dict(fixture["pages"])
    events = []
    initial = fixture["registers"]
    xmm = fixture["xmm"]
    regs = dict(initial)

    def event(op, at, value):
        if op == "write":
            p.store(pages, at, value)
        else:
            assert int.from_bytes(p.read_bytes(pages, at, 4), "little") == value
        events.append(dict(access=op, address=at, width=4, value=value))

    def write(at, value):
        event("write", at, value)

    def read(at, value):
        event("read", at, value)

    def boundary(endpoint, flags, mask):
        return dict(
            registers=dict(regs),
            xmm=dict(xmm),
            pages=dict(pages),
            events=copy.deepcopy(events),
            endpoint=endpoint,
            flags=flags,
            flag_mask=mask,
            df=0,
        )

    boundaries = {"parent_entry": boundary(0x49A8E0, 0x246, 0xFFFFFFFF)}
    for at, value in (
        (frame - 4, initial["ebp"]),
        (frame - 8, initial["esi"]),
        (frame - 12, initial["edi"]),
    ):
        write(at, value)
    read(frame + 4, j)
    for at in (h, h + 4, h + 8):
        write(at, 0)
    read(j + 4, o + 16)
    read(j, o)
    write(frame - 16, 2)
    write(frame - 20, 0x49A90C)
    regs.update(eax=2, esi=h, edi=j, ebp=frame - 4, esp=frame - 20)
    boundaries["reserve_entry"] = boundary(0x49AC40, 0, 0xC5)
    for at, value in ((frame - 24, frame - 4), (frame - 28, h), (frame - 32, j)):
        write(at, value)
    read(frame - 16, 2)
    for at in (h, h + 4, h + 8):
        write(at, 0)
    write(frame - 36, 2)
    write(frame - 40, 0x49AC78)
    regs.update(edi=2, ebp=frame - 24, esp=frame - 40)
    boundaries["allocation_entry"] = boundary(0x48A920, 0x95, 0x8D5)
    allocation_initial = dict(regs)
    at = frame - 40
    start = len(events)
    write(at - 4, regs["ebp"])
    read(at + 4, 2)
    for offset, value in ((-8, 16), (-12, 0x48A968), (-16, at - 4)):
        write(at + offset, value)
    read(at - 8, 16)
    for offset, value in ((-20, 16), (-24, 0x757507), (-28, at - 16)):
        write(at + offset, value)
    read(at - 28, at - 16)
    write(at - 28, at - 16)
    write(at - 32, regs["esi"])
    read(at - 20, 16)
    write(at - 36, 16)
    write(at - 40, 0)
    read(0x8B7634, 0x12345678)
    write(at - 44, 0x12345678)
    read(0x7D6220, 0x5000000)
    write(at - 48, 0x789463)
    regs.update(eax=16, esi=16, ebp=at - 28, esp=at - 48)
    imported = boundary(0x5000000, 0, 0x8C5)
    imported.update(entry_esp=frame - 88, words=[0x789463, 0x12345678, 0, 16])
    for address, value in (
        (at - 32, allocation_initial["esi"]),
        (at - 28, at - 16),
        (at - 24, 0x757507),
        (at - 20, 16),
        (at - 16, at - 4),
        (at - 12, 0x48A968),
        (at - 4, allocation_initial["ebp"]),
        (at, 0x49AC78),
    ):
        read(address, value)
    regs = dict(allocation_initial, eax=d, ecx=d, edx=0xB0000001, esp=at + 8)
    allocflags = add_flags(at - 8, 4)
    allocation_packet = dict(
        relation=dict(result=d, request=16, metadata=None),
        registers=dict(regs),
        flags=allocflags,
        flag_mask=0x8D5,
        stack=p.read_bytes(pages, 0x30000000, 8192),
        payload=p.read_bytes(pages, 0x6000000, 16384),
        events=copy.deepcopy(events[start:]),
    )
    boundaries["allocation_return"] = boundary(0x49AC78, allocflags, 0x8D5)
    write(h, d)
    write(h + 4, d)
    read(h, d)
    write(h + 8, d + 16)
    for address, value in (
        (frame - 32, j),
        (frame - 28, h),
        (frame - 24, frame - 4),
        (frame - 20, 0x49A90C),
    ):
        read(address, value)
    regs.update(eax=((d + 16) & 0xFFFFFF00) | 1, edi=j, ebp=frame - 4, esp=frame - 12)
    boundaries["reserve_return"] = boundary(0x49A90C, allocflags, 0x8D5)
    read(j + 4, o + 16)
    write(frame - 16, d)
    read(frame + 4, j)
    write(frame - 20, j)
    write(frame - 24, d)
    read(h, d)
    write(frame - 28, d)
    read(j, o)
    write(frame - 32, 0x49A921)
    regs.update(edx=o + 16, ecx=o, esp=frame - 32)
    boundaries["scalar_entry"] = boundary(0x48ABA0, 0, 0x8C5)
    scalar_packet = p.independent(
        dict(
            pages=dict(pages),
            registers=dict(regs),
            xmm=dict(xmm),
            source=o,
            destination=d,
            return_address=0x49A921,
            entry_flags=0x202,
        )
    )
    pages = dict(scalar_packet["pages"])
    events.extend(copy.deepcopy(scalar_packet["events"]))
    regs = dict(scalar_packet["registers"])
    boundaries["scalar_return"] = boundary(0x49A921, 0x44, 0x8D5)
    write(h + 4, d + 16)
    for address, value in (
        (frame - 12, initial["edi"]),
        (frame - 8, initial["esi"]),
        (frame - 4, initial["ebp"]),
        (frame, 0x4000000),
    ):
        read(address, value)
    regs.update(
        eax=h, esi=initial["esi"], edi=initial["edi"], ebp=initial["ebp"], esp=frame + 8
    )
    return dict(
        geometry=dict(
            entry=frame, source=o, destination=d, source_header=j, destination_header=h
        ),
        registers=regs,
        xmm=dict(xmm),
        flags=add_flags(frame - 28, 16),
        flag_mask=0x8D5,
        df=0,
        endpoint=0x4000000,
        pages=pages,
        events=events,
        trace_rvas=[f"0x{pc:08x}" for pc in TRACE],
        boundaries=boundaries,
        allocation_packet=allocation_packet,
        scalar_packet=scalar_packet,
        imported=imported,
        source_snapshot=p.read_bytes(fixture["pages"], o, 16),
    )


def check_packet(actual, vector, fixture):
    assert set(actual) == PACKET_KEYS
    p.assert_strict_packet(actual, independent(vector, fixture))
    assert len(actual["events"]) == 83 and len(actual["trace_rvas"]) == 136
    assert [len(b["events"]) for b in actual["boundaries"].values()] == [
        0,
        11,
        20,
        47,
        55,
        64,
        78,
    ]
    assert len(actual["imported"]["events"]) == 39
    assert len(actual["allocation_packet"]["events"]) == 27
    assert len(actual["scalar_packet"]["events"]) == 14


def expected_observation(vector, wanted):
    def record(state, name=None):
        raw = (
            state["flags"]
            if state["flag_mask"] == 0xFFFFFFFF
            else state["flags"] | 0x202
        )
        row = dict(
            registers=state["registers"],
            xmm=state["xmm"],
            eflags=raw,
            flags=state["flags"],
            flag_mask=state["flag_mask"],
            df=0,
            endpoint=state["endpoint"],
            pages_sha256=page_hashes(state["pages"]),
            events_sha256=canonical(state["events"]),
        )
        if name is not None:
            row["name"] = name
        return row

    imported = record(wanted["imported"])
    imported.update(
        role="allocation",
        entry_esp=wanted["imported"]["entry_esp"],
        words=wanted["imported"]["words"],
    )
    return dict(
        vector=dict(vector),
        registers=wanted["registers"],
        xmm=wanted["xmm"],
        flags=wanted["flags"],
        flag_mask=0x8D5,
        df=0,
        trace_rvas=wanted["trace_rvas"],
        events_sha256=canonical(wanted["events"]),
        pages_sha256=page_hashes(wanted["pages"]),
        memory_event_count=83,
        boundaries=[record(s, n) for n, s in wanted["boundaries"].items()],
        summaries=[imported],
    )


def sources():
    return {
        key: json.loads(
            (
                PROGRAMS
                / (
                    PREFIX
                    + (
                        "program_facts"
                        if key == "program_facts"
                        else kind.removeprefix("pe_")
                    )
                    + ".json"
                )
            ).read_text(encoding="utf-8")
        )
        for key, (kind, _) in SOURCE_PINS.items()
    }


def native_inputs():
    data, image, digest = c.common._load_executable(Path(os.environ["ITB_EXACT_EXE"]))
    assert digest == c.EXE_SHA256
    codes, points = c._load_code(data, image, sources())
    assert len(points) == 174 and sum(map(len, codes.values())) == 440
    allocation = [
        row
        for row in points
        if int(row["rva"], 16)
        in {
            int(q["rva"], 16)
            for body in sources()["allocation_conformance"]["bodies"].values()
            for q in body["points"]
        }
    ]
    assert (
        canonical(allocation)
        == "81d5140ea35625509678a4ca5204b8fb0dd6839199cf0f8673ee922fcb65ecbd"
    )
    return codes, points


def worker_packet(index):
    import unicorn as uc
    from unicorn import x86_const as x

    codes, points = native_inputs()
    vector = dict(alignment=(0, 7, 15)[index // 3], profile=index % 3)
    fixture = finite_fixture(vector)
    wanted = independent(vector, fixture)
    machines = []
    trace = []
    events = []
    boundaries = []
    summaries = []
    captured = {}
    real = uc.Uc

    def state(machine, mask):
        raw = machine.reg_read(x.UC_X86_REG_EFLAGS)
        return dict(
            registers={
                n: machine.reg_read(getattr(x, "UC_X86_REG_" + n.upper()))
                for n in p.GPRS
            },
            xmm={
                n: machine.reg_read(getattr(x, "UC_X86_REG_" + n.upper()))
                for n in p.XMMS
            },
            pages={
                base: bytes(machine.mem_read(base, 4096)) for base in fixture["pages"]
            },
            eflags=raw,
            flags=raw & mask,
            flag_mask=mask,
            df=(raw >> 10) & 1,
            endpoint=machine.reg_read(x.UC_X86_REG_EIP),
        )

    def own_code(machine, address, size, user):
        if address == 0x4000000:
            return
        if address == 0x5000000:
            actual = state(machine, 0x8C5)
            actual.update(
                events=copy.deepcopy(events),
                entry_esp=machine.reg_read(x.UC_X86_REG_ESP),
                words=[
                    int.from_bytes(
                        machine.mem_read(machine.reg_read(x.UC_X86_REG_ESP) + 4 * i, 4),
                        "little",
                    )
                    for i in range(4)
                ],
            )
            summaries.append(actual)
            return
        pc = address - 0x400000
        assert pc in set(TRACE)
        for name, expected in wanted["boundaries"].items():
            if address == expected["endpoint"]:
                boundaries.append(
                    dict(
                        name=name,
                        **state(machine, expected["flag_mask"]),
                        events=copy.deepcopy(events),
                    )
                )
        trace.append(f"0x{pc:08x}")

    def own_memory(machine, access, address, width, value, user):
        assert width == 4
        writing = access == uc.UC_MEM_WRITE
        events.append(
            dict(
                access="write" if writing else "read",
                address=address,
                width=4,
                value=(
                    value & 0xFFFFFFFF
                    if writing
                    else int.from_bytes(machine.mem_read(address, 4), "little")
                ),
            )
        )

    def observed(*args, **kwargs):
        machine = real(*args, **kwargs)
        machines.append(machine)
        original = machine.ctl_set_cpu_model
        attached = False

        def select_then_observe(cpu_model):
            nonlocal attached
            original(cpu_model)
            assert cpu_model == 19 and not attached
            machine.hook_add(uc.UC_HOOK_CODE, own_code)
            machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, own_memory)
            attached = True

        machine.ctl_set_cpu_model = select_then_observe
        return machine

    def capture(machine, ids, expected, installed):
        assert machine is machines[0] and set(ids) == set(p.GPRS)
        check_packet(expected, vector, fixture)
        p.assert_strict_packet(installed, fixture)
        captured.update(state(machine, 0x8D5))
        expected["boundaries"].clear()
        installed["pages"].clear()

    uc.Uc = observed
    try:
        observation = c._run_case(codes, points, vector, capture=capture)
    finally:
        uc.Uc = real
    assert len(machines) == 1 and machines[0].ctl_get_cpu_model() == 19
    p.assert_strict_packet(trace, wanted["trace_rvas"])
    p.assert_strict_packet(events, wanted["events"])
    assert len(boundaries) == 7 and len(summaries) == 1
    for actual, (name, expected) in zip(boundaries, wanted["boundaries"].items()):
        assert actual.pop("name") == name
        raw = actual.pop("eflags")
        assert raw == (
            expected["flags"]
            if expected["flag_mask"] == 0xFFFFFFFF
            else expected["flags"] | 0x202
        )
        p.assert_strict_packet(actual, expected)
    imported = summaries[0]
    assert imported.pop("eflags") == 0x202
    p.assert_strict_packet(imported, wanted["imported"])
    assert captured.pop("eflags") == wanted["flags"] | 0x202
    p.assert_strict_packet(
        captured,
        {
            k: wanted[k]
            for k in (
                "registers",
                "xmm",
                "pages",
                "flags",
                "flag_mask",
                "df",
                "endpoint",
            )
        },
    )
    assert set(observation) == OBS_KEYS
    assert all(set(b) == BOUNDARY_KEYS for b in observation["boundaries"])
    p.assert_strict_packet(observation, expected_observation(vector, wanted))


def worker_controls():
    codes, points = native_inputs()
    p.assert_strict_packet(c.CONTROLS, CONTROL_REASONS)
    assert len(CONTROL_REASONS) == 59
    for name, reason in CONTROL_REASONS.items():
        with pytest.raises(c.ConformanceError) as caught:
            c._run_case(codes, points, dict(alignment=15, profile=2), name)
        assert str(caught.value) == reason, name


def worker_direct_codes():
    import unicorn as uc

    codes, points = native_inputs()
    real = uc.Uc

    def forbidden(*args, **kwargs):
        raise AssertionError("forged code reached Uc")

    uc.Uc = forbidden
    try:
        for kind in (
            "floatkey",
            "extra",
            "missing",
            "mutable",
            "short",
            "byte",
            "missingpoint",
            "extrapoint",
            "reverse",
            "boolsize",
            "hash",
            "extra_point_field",
        ):
            code = copy.deepcopy(codes)
            rows = copy.deepcopy(points)
            start = min(code)
            if kind == "floatkey":
                code[float(start)] = code.pop(start)
            elif kind == "extra":
                code[1] = bytes(1)
            elif kind == "missing":
                code.pop(start)
            elif kind == "mutable":
                code[start] = bytearray(code[start])
            elif kind == "short":
                code[start] = code[start][:-1]
            elif kind == "byte":
                code[start] = bytes([code[start][0] ^ 1]) + code[start][1:]
            elif kind == "missingpoint":
                rows.pop()
            elif kind == "extrapoint":
                rows.append(copy.deepcopy(rows[0]))
            elif kind == "reverse":
                rows.reverse()
            elif kind == "boolsize":
                rows[0]["size"] = True
            elif kind == "hash":
                rows[0]["sha256"] = "0" * 64
            else:
                rows[0]["extra"] = 0
            with pytest.raises(c.ConformanceError):
                c._run_case(code, rows, dict(alignment=0, profile=0))
    finally:
        uc.Uc = real


def cli_arguments(command):
    args = [sys.executable, str(CLI), command]
    for key, (kind, _) in SOURCE_PINS.items():
        args += [
            "--" + key.replace("_", "-"),
            str(
                PROGRAMS
                / (
                    PREFIX
                    + (
                        "program_facts"
                        if key == "program_facts"
                        else kind.removeprefix("pe_")
                    )
                    + ".json"
                )
            ),
        ]
    if command != "verify-structure":
        args += ["--executable", os.environ["ITB_EXACT_EXE"]]
    if command != "build":
        args += ["--evidence", str(EVIDENCE)]
    return args


def worker_rebuild():
    p.assert_strict_packet(
        c.build_conformance(os.environ["ITB_EXACT_EXE"], sources()),
        json.loads(EVIDENCE.read_text(encoding="utf-8")),
    )


def worker_cli():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    for command in ("build", "verify", "verify-structure"):
        result = subprocess.run(
            cli_arguments(command), cwd=ROOT, capture_output=True, timeout=2400
        )
        assert result.returncode == 0, (result.stdout + result.stderr).decode(
            "utf-8", errors="replace"
        )[-4000:]
        value = json.loads(result.stdout)
        assert (
            result.stdout == c.encode_conformance(value).encode("utf-8")
            and b"\r" not in result.stdout
        )
        if command == "build":
            p.assert_strict_packet(value, evidence)
        else:
            p.assert_strict_packet(
                value,
                dict(
                    status=(
                        "verified" if command == "verify" else "structurally_verified"
                    ),
                    evidence_sha256=c.SEALED_SHA256,
                    summary=evidence["summary"],
                ),
            )


def isolated(action, index=0):
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("root must provide reviewed exact executable/runtime")
    env = os.environ.copy()
    env.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), action, str(index)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        timeout=2400,
    )
    assert result.returncode == 0, (result.stdout + result.stderr).decode(
        "utf-8", errors="replace"
    )[-5000:]


@pytest.mark.parametrize("index", range(9))
def test_actual_single_machine_ordered_pages_events_trace_and_seven_boundaries(index):
    isolated("packet", index)


def test_all_59_intended_machine_and_record_controls():
    isolated("controls")


def test_direct_code_forgeries_fail_before_uc():
    isolated("direct")


def test_exact_native_rebuild():
    isolated("rebuild")


def test_exact_three_cli_commands():
    isolated("cli")


@pytest.mark.parametrize("vector", recipes())
def test_complete_handwritten_finite_expected_packet(vector):
    fixture = finite_fixture(vector)
    p.assert_strict_packet(c._fixture(vector), fixture)
    check_packet(c._expected(vector, fixture), vector, fixture)


@pytest.mark.parametrize(
    "kind", ("bool", "float", "extra", "missing", "profile", "alignment", "list")
)
def test_vector_recipe_closed_schema(kind):
    vector = dict(alignment=0, profile=0)
    if kind == "bool":
        vector["alignment"] = False
    elif kind == "float":
        vector["profile"] = 0.0
    elif kind == "extra":
        vector["extra"] = 0
    elif kind == "missing":
        vector.pop("profile")
    elif kind == "profile":
        vector["profile"] = 3
    elif kind == "alignment":
        vector["alignment"] = 16
    else:
        vector = list(vector.items())
    with pytest.raises(c.ConformanceError):
        c._fixture(vector)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "boolflags",
        "gpr",
        "xmm",
        "source",
        "ancestor",
        "feature",
        "return",
    ),
)
def test_fixture_strict_fixed_recipe(kind):
    vector = dict(alignment=0, profile=0)
    fixture = finite_fixture(vector)
    if kind == "extra":
        fixture["extra"] = 0
    elif kind == "missing":
        fixture.pop("xmm")
    elif kind == "boolflags":
        fixture["entry_flags"] = True
    elif kind == "gpr":
        fixture["registers"]["eax"] ^= 1
    elif kind == "xmm":
        fixture["xmm"]["xmm7"] ^= 1
    elif kind == "return":
        fixture["return_address"] ^= 1
    else:
        at = {"source": 0x6002800, "ancestor": 0x30001008, "feature": 0x893001}[kind]
        p.store(fixture["pages"], at, p.read_bytes(fixture["pages"], at, 1)[0] ^ 1, 1)
    with pytest.raises(c.ConformanceError):
        c._expected(vector, fixture)


@pytest.mark.parametrize("child", ("allocation", "scalar"))
@pytest.mark.parametrize(
    "kind", ("extra", "missing", "bool", "gpr", "pages", "events", "coordinated")
)
def test_complete_child_join_rejects_corruption(child, kind, monkeypatch):
    vector = dict(alignment=0, profile=0)
    fixture = finite_fixture(vector)
    oracle = independent(vector, fixture)
    packet = copy.deepcopy(
        oracle["allocation_packet" if child == "allocation" else "scalar_packet"]
    )
    if child == "allocation":
        packet["events"][-1]["value"] = 0x4000000
    if kind == "extra":
        packet["extra"] = 0
    elif kind == "missing":
        packet.pop("flag_mask")
    elif kind == "bool":
        if child == "scalar":
            packet["df"] = False
        else:
            packet["flag_mask"] = float(packet["flag_mask"])
    elif kind == "gpr":
        packet["registers"]["edx"] ^= 1
    elif kind == "pages":
        if child == "scalar":
            p.store(packet["pages"], 0x893001, 0, 1)
        else:
            packet["payload"] = (
                bytes([packet["payload"][0] ^ 1]) + packet["payload"][1:]
            )
    elif kind == "events":
        packet["events"].pop()
    else:
        packet["registers"]["eax"] ^= 1
        if child == "allocation":
            packet["relation"]["result"] ^= 1
        else:
            packet["source_snapshot"] = bytes(16)
            p.store(packet["pages"], 0x6001000, 0)
        packet["events"][0]["value"] ^= 1
    target = c.allocator if child == "allocation" else c.scalar
    monkeypatch.setattr(
        target,
        "_expected" if child == "allocation" else "apply",
        lambda *args, **kwargs: copy.deepcopy(packet),
    )
    with pytest.raises(
        c.ConformanceError, match="path clone2 " + child + " primitive differs"
    ):
        c._expected(vector, fixture)


def test_installed_allocation_return_sentinel_guard():
    vector = dict(alignment=0, profile=0)
    oracle = independent(vector, finite_fixture(vector))
    state = oracle["boundaries"]["allocation_entry"]
    bad = dict(state["pages"])
    p.store(bad, state["registers"]["esp"], 0x4000000)
    with pytest.raises(c.ConformanceError, match="installed continuation differs"):
        c._allocation_packet_law(state["registers"], bad, 0x6001000, 0x49AC78)


def test_expected_and_fixture_do_not_mutate_or_alias():
    vector = dict(alignment=0, profile=0)
    fixture = finite_fixture(vector)
    before = copy.deepcopy(fixture)
    actual = c._expected(vector, fixture)
    check_packet(actual, vector, fixture)
    actual["boundaries"]["scalar_entry"]["pages"].clear()
    actual["allocation_packet"]["events"].clear()
    actual["scalar_packet"]["xmm"].clear()
    actual["imported"]["words"].clear()
    p.assert_strict_packet(fixture, before)
    check_packet(c._expected(vector, fixture), vector, fixture)


@pytest.fixture
def receipt():
    if not EVIDENCE.is_file():
        pytest.skip("root must publish sealed receipt")
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def test_published_receipt_exact_source_sites_scope_and_independent_corpus(receipt):
    assert canonical(receipt) == c.SEALED_SHA256
    assert EVIDENCE.read_bytes() == c.encode_conformance(receipt).encode("utf-8")
    assert b"\r" not in EVIDENCE.read_bytes()
    assert receipt["analysis_kind"] == "pe_native_movement_path_clone2_conformance"
    p.assert_strict_packet(c.SOURCE_PINS, SOURCE_PINS)
    p.assert_strict_packet(receipt["vectors"], recipes())
    p.assert_strict_packet(c.vectors(), recipes())
    supplied = sources()
    assert receipt["build_identity"] == supplied["program_facts"]["identity"]
    assert set(receipt["source_receipts"]) == set(SOURCE_PINS)
    for key, (kind, digest) in SOURCE_PINS.items():
        assert canonical(supplied[key]) == digest
        assert receipt["source_receipts"][key]["canonical_sha256"] == digest
        assert supplied[key]["analysis_kind"] == kind
    atlas = {
        int(row["entry_rva"], 16): row for row in supplied["program_facts"]["functions"]
    }
    ranges = receipt["body"]["ranges"]
    assert [int(row["start_rva"], 16) for row in ranges] == [
        0x8A920,
        0x8ABA0,
        0x9A8E0,
        0x9AC40,
        0x3574DB,
        0x379F52,
        0x38942B,
    ]
    for row in ranges:
        start = int(row["start_rva"], 16)
        end = int(row["exclusive_end_rva"], 16)
        assert end - start == atlas[start]["body_size"]
        assert row["sha256"] == atlas[start]["body_sha256"]
    points = receipt["body"]["points"]
    assert len(points) == 174 and sum(row["size"] for row in points) == 440
    assert len({row["rva"] for row in points}) == 174
    assert points == sorted(points, key=lambda row: int(row["rva"], 16))
    for row in ranges:
        start = int(row["start_rva"], 16)
        end = int(row["exclusive_end_rva"], 16)
        cursor = start
        for point in points:
            at = int(point["rva"], 16)
            if start <= at < end:
                assert at == cursor and type(point["size"]) is int
                assert set(point) == {"rva", "size", "sha256"}
                cursor += point["size"]
        assert cursor == end
    p.assert_strict_packet(
        receipt["executed_rvas"], sorted({f"0x{pc:08x}" for pc in TRACE})
    )
    observations = [
        expected_observation(v, independent(v, finite_fixture(v))) for v in recipes()
    ]
    assert receipt["observations_sha256"] == canonical(observations)
    assert receipt["engine"] == dict(
        name="Unicorn",
        version="2.1.4",
        architecture="x86_32",
        cpu_model=dict(id=19, name="UC_CPU_X86_HASWELL"),
    )
    p.assert_strict_packet(
        receipt["summary"],
        dict(
            cases=48,
            loaded_sites=174,
            loaded_bytes=440,
            executed_sites=126,
            native_instructions=6528,
            memory_events=3984,
            allocation_requests=48,
            allocation_request_bytes=768,
            free_requests=0,
            copied_bytes=768,
            source_bytes_preserved=768,
            xmm_preserved_cases=48,
            scalar_iterations=96,
            wide_reads=0,
            wide_writes=0,
            controls=59,
            opaque_instructions=0,
            effect_record_sites=0,
            accounting_promotions=0,
        ),
    )
    p.assert_strict_packet(
        receipt["negative_controls"],
        [
            dict(name=name, rejected=True, reason=reason)
            for name, reason in CONTROL_REASONS.items()
        ],
    )
    assert len(set(CONTROL_REASONS)) == 59
    scope = " ".join(receipt["scope"]["premises"] + receipt["scope"]["not_claimed"])
    assert "ordinary count-two" in scope and "seven native boundaries" in scope
    assert "record mutations" in scope and "AddMove count greater than one" in scope


@pytest.mark.parametrize(
    "kind",
    (
        "summary",
        "bool_summary",
        "vector",
        "control",
        "point",
        "range",
        "observations",
        "pin",
        "scope",
        "extra",
    ),
)
def test_sealed_receipt_forgeries(kind, receipt):
    bad = copy.deepcopy(receipt)
    if kind == "summary":
        bad["summary"]["copied_bytes"] += 1
    elif kind == "bool_summary":
        bad["summary"]["free_requests"] = False
    elif kind == "vector":
        bad["vectors"][0]["alignment"] = False
    elif kind == "control":
        bad["negative_controls"][0]["rejected"] = False
    elif kind == "point":
        bad["body"]["points"][0]["size"] += 1
    elif kind == "range":
        bad["body"]["ranges"][0]["sha256"] = "0" * 64
    elif kind == "observations":
        bad["observations_sha256"] = "0" * 64
    elif kind == "pin":
        bad["source_receipts"]["movement_binding"]["canonical_sha256"] = "0" * 64
    elif kind == "scope":
        bad["scope"]["claim"] = "whole game ownership"
    else:
        bad["extra"] = 0
    with pytest.raises(c.ConformanceError):
        c.validate_structure(bad, sources())


@pytest.mark.parametrize(
    "kind",
    (
        "missing",
        "extra",
        "nonmapping",
        "kind",
        "body",
        "build",
        "nonfinite",
        "atlas",
        "allocationjoin",
    ),
)
def test_source_identity_and_refreshed_pin_joins(kind, monkeypatch):
    supplied = sources()
    if kind == "missing":
        supplied.pop("movement_binding")
    elif kind == "extra":
        supplied["extra"] = {}
    elif kind == "nonmapping":
        supplied = list(supplied.values())
    elif kind == "kind":
        supplied["movement_binding"]["analysis_kind"] = "forged"
    elif kind == "body":
        supplied["movement_binding"]["bodies"]["move_parent"]["size"] += 1
    elif kind == "nonfinite":
        supplied["movement_binding"]["bad"] = float("nan")
    else:
        key = (
            "movement_binding"
            if kind == "build"
            else "program_facts" if kind == "atlas" else "allocation_conformance"
        )
        if kind == "build":
            supplied[key]["build_identity"]["executable_sha256"] = "0" * 64
        elif kind == "atlas":
            row = next(
                r for r in supplied[key]["functions"] if r["entry_rva"] == "0x0008aba0"
            )
            row["body_size"] += 1
        else:
            supplied[key]["source_composition_sha256"] = "0" * 64
        changed = dict(c.SOURCE_PINS)
        changed[key] = (changed[key][0], canonical(supplied[key]))
        monkeypatch.setattr(c, "SOURCE_PINS", changed)
    with pytest.raises(c.ConformanceError):
        c._preflight(supplied)


@pytest.mark.parametrize("key", tuple(SOURCE_PINS))
def test_every_source_pin_closed(key):
    supplied = sources()
    supplied[key]["extra"] = 0
    with pytest.raises(c.ConformanceError):
        c._preflight(supplied)


def test_structure_summary_detached(receipt):
    result = c.validate_structure(receipt, sources())
    result["summary"]["cases"] = 0
    assert receipt["summary"]["cases"] == 48


def test_encoder_strict_utf8_and_nonfinite(receipt):
    assert c.encode_conformance({"text": "café"}) == '{\n  "text": "café"\n}\n'
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            c.encode_conformance({"bad": value})
    bad = copy.deepcopy(receipt)
    bad["summary"]["cases"] = float("nan")
    with pytest.raises(c.ConformanceError):
        c.validate_structure(bad, sources())


@pytest.mark.parametrize(
    "kind", ("noncanonical", "duplicate", "nonfinite", "invalid_utf8")
)
def test_cli_malformed_evidence_rejects(tmp_path, receipt, kind):
    raw = c.encode_conformance(receipt).encode()
    if kind == "noncanonical":
        raw = b" " + raw
    elif kind == "duplicate":
        raw = b'{"analysis_kind":"a","analysis_kind":"b"}\n'
    elif kind == "nonfinite":
        raw = b'{"value":NaN}\n'
    else:
        raw = b"\xff"
    path = tmp_path / "malformed.json"
    path.write_bytes(raw)
    args = cli_arguments("verify-structure")
    args[-1] = str(path)
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=120)
    assert (
        result.returncode == 1 and result.stdout == b"" and b"error:" in result.stderr
    )


if __name__ == "__main__":
    action = sys.argv[1]
    index = int(sys.argv[2])
    {
        "packet": lambda: worker_packet(index),
        "controls": worker_controls,
        "direct": worker_direct_codes,
        "rebuild": worker_rebuild,
        "cli": worker_cli,
    }[action]()
